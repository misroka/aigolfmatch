"""Fixed, identifier-free features and additive signed explanations."""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

FEATURE_NAMES = [
    "skill_fit", "shaft_speed_fit", "loft_preference_fit", "price_to_budget",
    "missing_skill", "missing_shaft_speed", "missing_loft", "missing_price_budget",
]
BASE_INTERCEPT = 0.2
BASE_COEFFICIENTS = [0.12, 0.14, 0.10, 0.04, -0.04, -0.04, -0.04, -0.04]
OBJECTIVE = "carry_yards / 400 - dispersion_yards / 150"
LIMITATIONS = [
    "Utility is a carry/dispersion proxy, not a true best club or causal fitting efficacy.",
    "Heuristic fit assumptions and observational outcomes may not generalize; verify with a fitter.",
]
SKILLS = {"beginner": 0, "intermediate": 1, "advanced": 2, "professional": 3}
FLEX = {
    "ladies": 60, "l": 60, "senior": 75, "a": 75, "regular": 90, "r": 90,
    "stiff": 105, "s": 105, "extra stiff": 120, "extra-stiff": 120, "x": 120,
}
CLUB_TYPES = {"driver", "fairway wood", "hybrid", "iron", "wedge", "putter"}


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def text(value):
    return str(value).strip().lower() if value is not None else ""


def timestamp(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo and parsed.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def club_type(record):
    return text(record.get("club_type") or record.get("club_type_name"))


def handedness(value):
    return {"right": "right", "r": "right", "left": "left", "l": "left", "both": "both"}.get(text(value))


def features(profile, club, price=None):
    specs = club.get("specifications")
    specs = specs if isinstance(specs, dict) else {}
    skill = SKILLS.get(text(profile.get("skill_level")))
    target = SKILLS.get(text(club.get("skill_level")))
    speed = number(profile.get("swing_speed_mph"))
    flex = FLEX.get(text(specs.get("shaft_flex", club.get("shaft_flex"))))
    loft = number(specs.get("loft_degrees", club.get("loft_degrees")))
    preferred = number(profile.get("preferred_loft", profile.get("loft_preference")))
    budget = number(profile.get("budget"))
    price = number(price if price is not None else club.get("price", club.get("current_price")))
    missing = [
        skill is None or target is None,
        speed is None or speed <= 0 or flex is None,
        loft is None or not 0 <= loft <= 90 or preferred is None or not 0 <= preferred <= 90,
        price is None or price < 0 or budget is None or budget <= 0,
    ]
    values = [
        0 if missing[0] else 1 - abs(skill - target) / 3,
        0 if missing[1] else max(0, 1 - abs(speed - flex) / 40),
        0 if missing[2] else max(0, 1 - abs(loft - preferred) / 20),
        0 if missing[3] else max(-1, min(1, 1 - price / budget)),
    ]
    return values + [float(flag) for flag in missing]


def predict(values, intercept, coefficients):
    return intercept + sum(x * weight for x, weight in zip(values, coefficients))


def quality_passes(evaluation):
    """Require independent cold-golfer holdout, ranking and cold-club evidence."""
    try:
        counts = evaluation["counts"]
        all_metrics = evaluation["cold_golfer"]
        new_metrics = evaluation["new_club"]
        ranking = evaluation["ranking"]
        return (
            counts["train_golfers"] >= 20 and counts["test_golfers"] >= 8
            and counts["train_rows"] >= 60 and counts["test_rows"] >= 20
            and counts["train_clubs"] >= 5 and counts["test_clubs"] >= 3
            and counts["overlapping_golfers"] == 0
            and new_metrics["rows"] >= 5 and new_metrics["golfers"] >= 2
            and ranking["golfers"] >= 5
            and all_metrics["baseline_mae"] - all_metrics["model_mae"] >= 0.01
            and all_metrics["model_mae"] <= 0.9 * all_metrics["baseline_mae"]
            and new_metrics["model_mae"] <= new_metrics["baseline_mae"]
            and ranking["model_ndcg"] >= ranking["baseline_ndcg"] + 0.01
        )
    except (KeyError, TypeError):
        return False


def _finite_tree(value):
    if isinstance(value, dict):
        return all(_finite_tree(v) for v in value.values())
    if isinstance(value, list):
        return all(_finite_tree(v) for v in value)
    return not isinstance(value, (float, int)) or (not isinstance(value, bool) and math.isfinite(value))


def validate_model(model):
    if not isinstance(model, dict) or not _finite_tree(model):
        raise ValueError("Model must be a finite JSON object.")
    if model.get("version") != 1 or model.get("feature_names") != FEATURE_NAMES or model.get("objective") != OBJECTIVE:
        raise ValueError("Unsupported model version, objective or feature schema.")
    coefficients = model.get("coefficients")
    if not isinstance(coefficients, list) or len(coefficients) != len(FEATURE_NAMES):
        raise ValueError("Invalid model coefficients.")
    numeric = coefficients + [model.get("intercept"), model.get("residual_mae")]
    if any(not isinstance(v, (float, int)) or isinstance(v, bool) or number(v) is None for v in numeric):
        raise ValueError("Model parameters must be finite numbers.")
    if any(abs(v) > 1000 for v in numeric):
        raise ValueError("Model parameters exceed the supported proxy utility scale.")
    if model["residual_mae"] < 0:
        raise ValueError("Residual error cannot be negative.")
    if not isinstance(model.get("training_club_ids"), list) or any(
        not isinstance(v, str) for v in model["training_club_ids"]
    ):
        raise ValueError("Invalid training club metadata.")
    evaluation = model.get("evaluation")
    if not isinstance(evaluation, dict):
        raise ValueError("Missing evaluation evidence.")
    try:
        count_names = (
            "train_rows", "test_rows", "train_golfers", "test_golfers",
            "train_clubs", "test_clubs", "overlapping_golfers", "purged_rows",
        )
        counts = [evaluation["counts"][key] for key in count_names]
        for subset in ("cold_golfer", "new_club"):
            metrics = evaluation[subset]
            counts.extend([metrics["rows"], metrics["golfers"]])
            for key in ("model_mae", "baseline_mae"):
                value = metrics[key]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1000:
                    raise ValueError("Invalid evaluation residual metric.")
        ranking = evaluation["ranking"]
        counts.append(ranking["golfers"])
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in counts):
            raise ValueError("Evaluation group counts must be nonnegative integers.")
        for key in ("model_ndcg", "baseline_ndcg"):
            if not isinstance(ranking[key], (int, float)) or not 0 <= ranking[key] <= 1:
                raise ValueError("Invalid NDCG.")
        if model["residual_mae"] != evaluation["cold_golfer"]["model_mae"]:
            raise ValueError("Residual uncertainty must equal the heldout MAE.")
        if evaluation["cold_golfer"]["rows"] != evaluation["counts"]["test_rows"]:
            raise ValueError("Inconsistent holdout row counts.")
    except (KeyError, TypeError) as exc:
        raise ValueError("Incomplete evaluation schema.") from exc
    if model.get("quality_gate") not in ("passed", "failed"):
        raise ValueError("Invalid quality gate.")
    if model["quality_gate"] == "passed" and not quality_passes(evaluation):
        raise ValueError("Model does not satisfy the independent evaluation quality gate.")
    return model


def load_model(path):
    """Read JSON only from the caller's configured local path; missing means baseline."""
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as handle:
            if path.stat().st_size > 2_000_000:
                raise ValueError("Model artifact is too large.")
            model = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to read a valid JSON model artifact.") from exc
    return validate_model(model)


def _eligible_offer(profile, club, now):
    desired_type = club_type(profile)
    hand = handedness(profile.get("hand"))
    budget = number(profile.get("budget"))
    if desired_type not in CLUB_TYPES or hand not in ("left", "right") or budget is None or budget < 0:
        return None
    if club_type(club) != desired_type or handedness(club.get("hand")) not in (hand, "both"):
        return None
    offers = club.get("product_sources", club.get("prices"))
    offers = offers if isinstance(offers, list) else [club]
    eligible = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        price = number(offer.get("price"))
        checked = timestamp(offer.get("checked_at", offer.get("price_checked_at", offer.get("last_checked"))))
        if (offer.get("in_stock") is True and price is not None and 0 <= price <= budget
                and checked is not None and timedelta(0) <= now - checked <= timedelta(hours=24)):
            eligible.append((price, offer))
    return min(eligible, key=lambda item: item[0]) if eligible else None


def recommend(profile, candidates, model=None, limit=5):
    """Rank constraint-eligible clubs with exact signed local contributions.

    Scores have proxy utility units, not probabilities. Model uncertainty is heldout
    mean absolute residual error, not a calibrated confidence interval.
    """
    if not isinstance(profile, dict) or not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return []
    if model is not None:
        model = validate_model(model)
    trained = model is not None and model["quality_gate"] == "passed"
    intercept = model["intercept"] if trained else BASE_INTERCEPT
    coefficients = model["coefficients"] if trained else BASE_COEFFICIENTS
    now = datetime.now(timezone.utc)
    results = []
    for club in candidates:
        if not isinstance(club, dict):
            continue
        offer = _eligible_offer(profile, club, now)
        if offer is None:
            continue
        price, source = offer
        values = features(profile, club, price)
        contributions = [
            {"feature": name, "value": value, "contribution": value * coefficient}
            for name, value, coefficient in zip(FEATURE_NAMES, values, coefficients)
        ]
        missing = [name for name, value in zip(FEATURE_NAMES[4:], values[4:]) if value]
        unseen = not trained or str(club.get("id")) not in model["training_club_ids"]
        limitations = list(LIMITATIONS)
        if not trained:
            limitations.append("No quality-gated trained model available; using transparent heuristic baseline.")
        if missing:
            limitations.append("Missing profile/specification features: " + ", ".join(missing))
        if unseen:
            limitations.append("Cold-start club: no training outcome coverage; generalization is unverified.")
        results.append({
            "id": club.get("id"), "club": dict(club), "price": price,
            "source_name": source.get("source_name"),
            "score": intercept + sum(item["contribution"] for item in contributions),
            "method": "supervised_ridge" if trained else "baseline",
            "contributions": contributions, "baseline_value": intercept,
            "uncertainty": {
                "heldout_mae": model["residual_mae"] if trained else None,
                "calibrated": False, "cold_start": unseen, "missing_features": missing,
                "description": "Heldout mean absolute residual error; not calibrated confidence.",
            },
            "limitations": limitations,
        })
    return sorted(results, key=lambda row: (-row["score"], str(row["id"])))[:limit]
