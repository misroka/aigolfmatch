"""Chronological, cold-golfer evaluation of measured fitting outcomes only."""

import math
from collections import defaultdict
from datetime import datetime, timezone

from .engine import (
    BASE_COEFFICIENTS, BASE_INTERCEPT, FEATURE_NAMES, OBJECTIVE,
    features, number, predict, quality_passes, timestamp, validate_model,
)


class InsufficientDataError(ValueError):
    """More independent measured outcomes are required before training."""


def _metrics(rows, predictions, baseline):
    return {
        "rows": len(rows),
        "golfers": len({r["golfer_id"] for r in rows}),
        "model_mae": sum(abs(r["target"] - p) for r, p in zip(rows, predictions)) / len(rows),
        "baseline_mae": sum(abs(r["target"] - p) for r, p in zip(rows, baseline)) / len(rows),
    } if rows else {"rows": 0, "golfers": 0, "model_mae": 0.0, "baseline_mae": 0.0}


def _ranking(rows, predictions, baseline):
    # Average repeated measurements of a club before ranking unique clubs per golfer.
    groups = defaultdict(lambda: defaultdict(list))
    for row, pred, base in zip(rows, predictions, baseline):
        groups[row["golfer_id"]][row["club_id"]].append((row["target"], pred, base))
    model_scores, baseline_scores = [], []
    for clubs in groups.values():
        values = [tuple(sum(v[i] for v in shots) / len(shots) for i in range(3)) for shots in clubs.values()]
        if len(values) < 2:
            continue
        minimum, maximum = min(v[0] for v in values), max(v[0] for v in values)
        if maximum - minimum < 1e-12:
            continue
        gains = [(v[0] - minimum) / (maximum - minimum) for v in values]
        ideal = sum(g / math.log2(i + 2) for i, g in enumerate(sorted(gains, reverse=True)))
        for index, scores in ((1, model_scores), (2, baseline_scores)):
            # Average tied prediction ranks, avoiding arbitrary row-order advantages.
            dcg, start = 0.0, 0
            order = sorted(range(len(values)), key=lambda i: values[i][index], reverse=True)
            while start < len(order):
                end = start + 1
                while end < len(order) and values[order[end]][index] == values[order[start]][index]:
                    end += 1
                mean_gain = sum(gains[i] for i in order[start:end]) / (end - start)
                dcg += mean_gain * sum(1 / math.log2(i + 2) for i in range(start, end))
                start = end
            scores.append(max(0.0, min(1.0, dcg / ideal)))
    return {
        "golfers": len(model_scores),
        "model_ndcg": sum(model_scores) / len(model_scores) if model_scores else 0.0,
        "baseline_ndcg": sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0.0,
    }


def _prepare(outcomes):
    rows = []
    seen_ids = set()
    now = datetime.now(timezone.utc)
    for index, row in enumerate(outcomes):
        if not isinstance(row, dict):
            raise ValueError(f"Outcome {index}: expected an object.")
        identifier = str(row.get("id", ""))
        if (not identifier.isascii() or not identifier.isdecimal() or int(identifier) <= 0
                or identifier in seen_ids):
            raise ValueError(f"Outcome {index}: require a unique positive database id for consent revalidation.")
        seen_ids.add(identifier)
        when = timestamp(row.get("measured_at"))
        carry, dispersion, shots = (number(row.get(key)) for key in ("carry_yards", "dispersion_yards", "shot_count"))
        if (when is None or when > now or carry is None or not 0 <= carry <= 400
                or dispersion is None or not 0 <= dispersion <= 150
                or shots is None or shots != int(shots) or not 5 <= shots <= 500):
            raise ValueError(f"Outcome {index}: require aware past measured_at, carry 0–400, dispersion 0–150 and 5–500 shots.")
        if (not isinstance(row.get("profile"), dict) or not isinstance(row.get("club"), dict)
                or row.get("golfer_id") in (None, "") or row.get("club_id") in (None, "")):
            raise ValueError(f"Outcome {index}: require golfer_id, club_id and profile/club snapshots.")
        rows.append({
            "id": identifier,
            "golfer_id": str(row["golfer_id"]), "club_id": str(row["club_id"]),
            "when": when, "values": features(row["profile"], row["club"]),
            "target": carry / 400 - dispersion / 150,
        })
    return sorted(rows, key=lambda row: row["when"])


def train_model(outcomes):
    """Return a JSON-compatible artifact, including failed evaluation evidence.

    Split the latest quarter of timestamp blocks first, then purge all holdout
    golfer IDs from training. Never refit on the test set. The CLI saves only a
    passed artifact; callers must not present a failed artifact as validated ML.
    """
    rows = _prepare(outcomes)
    times = sorted({row["when"] for row in rows})
    if len(times) < 4:
        raise InsufficientDataError("Need at least four distinct measurement time blocks and independent golfers.")
    cutoff = times[max(1, int(len(times) * 0.75))]
    test = [row for row in rows if row["when"] >= cutoff]
    test_golfers = {row["golfer_id"] for row in test}
    train = [row for row in rows if row["when"] < cutoff and row["golfer_id"] not in test_golfers]
    counts = {
        "train_rows": len(train), "test_rows": len(test),
        "train_golfers": len({r["golfer_id"] for r in train}),
        "test_golfers": len(test_golfers),
        "train_clubs": len({r["club_id"] for r in train}),
        "test_clubs": len({r["club_id"] for r in test}),
        "overlapping_golfers": len({r["golfer_id"] for r in train} & test_golfers),
        "purged_rows": sum(r["when"] < cutoff and r["golfer_id"] in test_golfers for r in rows),
    }
    if (counts["train_rows"] < 60 or counts["test_rows"] < 20
            or counts["train_golfers"] < 20 or counts["test_golfers"] < 8
            or counts["train_clubs"] < 5 or counts["test_clubs"] < 3):
        raise InsufficientDataError(
            "Need >=60 train/20 test measured outcomes, >=20 train/8 unseen test golfers, "
            "and >=5 train/3 test clubs after chronological split and golfer purge. "
            "Collect consented independent fitting sessions; do not generate labels."
        )
    from sklearn.linear_model import Ridge

    estimator = Ridge(alpha=1.0)
    estimator.fit([row["values"] for row in train], [row["target"] for row in train])
    intercept = float(estimator.intercept_)
    coefficients = [float(value) for value in estimator.coef_]
    predictions = [predict(r["values"], intercept, coefficients) for r in test]
    baseline = [predict(r["values"], BASE_INTERCEPT, BASE_COEFFICIENTS) for r in test]
    known_clubs = {row["club_id"] for row in train}
    cold_indices = [i for i, row in enumerate(test) if row["club_id"] not in known_clubs]
    evaluation = {
        "split": "latest_timestamp_quarter_then_purge_overlapping_golfers",
        "holdout_start": cutoff.isoformat(), "counts": counts,
        "cold_golfer": _metrics(test, predictions, baseline),
        "new_club": _metrics([test[i] for i in cold_indices], [predictions[i] for i in cold_indices], [baseline[i] for i in cold_indices]),
        "ranking": _ranking(test, predictions, baseline),
        "gate_policy": "MAE improves >=10% and >=0.01; NDCG improves >=0.01 for >=5 golfers; new-club MAE not worse (>=5 rows, >=2 golfers).",
    }
    artifact = {
        "version": 1, "feature_names": list(FEATURE_NAMES), "objective": OBJECTIVE,
        "intercept": intercept, "coefficients": coefficients,
        "residual_mae": evaluation["cold_golfer"]["model_mae"],
        "evaluation": evaluation, "quality_gate": "passed" if quality_passes(evaluation) else "failed",
        "training_club_ids": sorted(known_clubs),
        "outcome_ids": sorted({row["id"] for row in rows}, key=int),
        "trained_at": now_iso(),
        "limitations": ["Observational proxy objective, not causal efficacy or a true best-club label.",
                        "Residual MAE is not a calibrated confidence interval."],
    }
    return validate_model(artifact)


def now_iso():
    return datetime.now(timezone.utc).isoformat()
