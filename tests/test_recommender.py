"""Synthetic unit fixtures test mechanics, not real-world model validation."""

import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from recommender import FEATURE_NAMES, InsufficientDataError, load_model, recommend, train_model
from recommender.engine import features


def profile():
    return {"club_type": "Driver", "hand": "Right", "budget": 500,
            "skill_level": "beginner", "swing_speed_mph": 90, "preferred_loft": 10}


def club(identifier=1):
    return {
        "id": identifier, "model_name": "Fixture only", "club_type_name": "Driver",
        "hand": "Both", "skill_level": "beginner", "shaft_flex": "Regular",
        "loft_degrees": 10, "price": 200, "in_stock": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def synthetic_outcomes():
    """Analytic test function deliberately unlike the heuristic; never production data."""
    rows = []
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    skills = ["beginner", "intermediate", "advanced", "professional"]
    for golfer in range(64):
        for variant in range(4):
            p = profile()
            c = club((variant % 6) if golfer < 48 else ("new-" + str(variant)))
            c["id"] = (golfer + variant) % 8 if golfer < 48 else "new-" + str(variant)
            c["skill_level"] = skills[variant]
            c["price"] = 100 + variant * 100
            values = features(p, c)
            target = 0.85 - 0.60 * values[0] + 0.05 * values[3]
            rows.append({
                "id": len(rows) + 1,
                "profile": p, "club": c, "golfer_id": str(golfer), "club_id": str(c["id"]),
                "measured_at": (start + timedelta(days=golfer)).isoformat(),
                "carry_yards": (target + 0.1) * 400, "dispersion_yards": 15, "shot_count": 10,
            })
    return rows


class RecommendationTests(unittest.TestCase):
    def test_baseline_decomposition_and_cold_start(self):
        result = recommend(profile(), [club()])[0]
        self.assertEqual(result["method"], "baseline")
        self.assertEqual(result["model_name"], "Fixture only")
        self.assertAlmostEqual(result["score"], result["baseline_value"] +
                               sum(item["contribution"] for item in result["contributions"]))
        self.assertEqual([x["feature"] for x in result["contributions"]], FEATURE_NAMES)
        self.assertTrue(result["uncertainty"]["cold_start"])
        self.assertIsNone(result["uncertainty"]["heldout_mae"])
        self.assertFalse(result["uncertainty"]["calibrated"])

    def test_hard_constraints_fail_closed(self):
        changes = [
            {"hand": None}, {"hand": "Left"}, {"club_type_name": "Iron"},
            {"club_type_name": None}, {"price": 501}, {"price": -1},
            {"price": float("nan")}, {"price": float("inf")},
            {"in_stock": None}, {"in_stock": 1}, {"in_stock": "True"},
            {"checked_at": datetime.now().isoformat()},
            {"checked_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()},
            {"checked_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        ]
        for change in changes:
            with self.subTest(change=change):
                candidate = club()
                candidate.update(change)
                self.assertEqual(recommend(profile(), [candidate]), [])
        for change in ({"budget": None}, {"budget": float("inf")}, {"budget": True},
                       {"hand": None}, {"club_type": "unknown"}):
            p = profile()
            p.update(change)
            self.assertEqual(recommend(p, [club()]), [])

    def test_budget_uses_fresh_available_offer_not_cached_price(self):
        c = club()
        c["price_checked_at"] = c.pop("checked_at")
        self.assertEqual(recommend(profile(), [c])[0]["price"], 200)
        c["current_price"] = 1
        c["product_sources"] = [
            {"price": 1, "in_stock": False, "checked_at": c["price_checked_at"]},
            {"price": 300, "in_stock": True, "checked_at": c["price_checked_at"]},
        ]
        self.assertEqual(recommend(profile(), [c])[0]["price"], 300)
        c["product_sources"][1]["price"] = 600
        self.assertEqual(recommend(profile(), [c]), [])

    def test_price_check_timestamp_has_priority_over_scrape_timestamp(self):
        c = club()
        c["price_checked_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.assertEqual(recommend(profile(), [c]), [])
        c["price_checked_at"] = None
        self.assertEqual(recommend(profile(), [c]), [])

    def test_missing_specs_signed_penalty_and_ids_not_predictors(self):
        c = club()
        del c["shaft_flex"]
        result = recommend(profile(), [c])[0]
        missing = next(x for x in result["contributions"] if x["feature"] == "missing_shaft_speed")
        self.assertLess(missing["contribution"], 0)
        self.assertIn("missing_shaft_speed", result["uncertainty"]["missing_features"])
        before = features(profile(), c)
        c.update(id=9999, brand_id=444, club_type_id=222)
        self.assertEqual(before, features(profile(), c))

    def test_canonical_profile_loft_degrees(self):
        p = profile()
        del p["preferred_loft"]
        p["loft_degrees"] = 10
        self.assertEqual(features(p, club())[2], 1)
        self.assertEqual(features(p, club())[6], 0)
        p["loft_degrees"] = 30
        self.assertEqual(features(p, club())[2], 0)

    def test_limit_and_deterministic_sort(self):
        self.assertEqual(len(recommend(profile(), [club(2), club(1)], limit=1)), 1)
        self.assertEqual(recommend(profile(), [club(2), club(1)])[0]["id"], 1)
        self.assertEqual(recommend(profile(), [club()], limit=-1), [])

    def test_insufficient_data_no_artificial_fallback_labels(self):
        with self.assertRaises(InsufficientDataError):
            train_model([])
        rows = synthetic_outcomes()[:10]
        with self.assertRaises(InsufficientDataError):
            train_model(rows)

    def test_chronological_grouped_evaluation_and_signed_ml(self):
        artifact = train_model(synthetic_outcomes())
        self.assertEqual(artifact["quality_gate"], "passed")
        evaluation = artifact["evaluation"]
        self.assertEqual(evaluation["counts"]["overlapping_golfers"], 0)
        self.assertGreaterEqual(evaluation["ranking"]["golfers"], 5)
        self.assertGreater(evaluation["ranking"]["model_ndcg"], evaluation["ranking"]["baseline_ndcg"])
        self.assertLess(evaluation["cold_golfer"]["model_mae"], evaluation["cold_golfer"]["baseline_mae"])
        result = recommend(profile(), [club("new-club")], artifact)[0]
        self.assertEqual(result["method"], "supervised_ridge")
        self.assertTrue(any(x["contribution"] < 0 for x in result["contributions"]))
        self.assertAlmostEqual(result["score"], result["baseline_value"] +
                               sum(x["contribution"] for x in result["contributions"]))

    def test_purges_earlier_measurements_of_holdout_golfers(self):
        rows = synthetic_outcomes()
        duplicate = copy.deepcopy(rows[-1])
        duplicate["id"] = len(rows) + 1
        duplicate["measured_at"] = "2019-01-01T00:00:00+00:00"
        artifact = train_model(rows + [duplicate])
        self.assertGreaterEqual(artifact["evaluation"]["counts"]["purged_rows"], 1)
        self.assertEqual(artifact["evaluation"]["counts"]["overlapping_golfers"], 0)
        self.assertEqual(set(artifact["outcome_ids"]), {str(row["id"]) for row in rows + [duplicate]})

    def test_weak_model_falls_back(self):
        rows = synthetic_outcomes()
        for row in rows:
            row["carry_yards"] = 200
            row["dispersion_yards"] = 30
        artifact = train_model(rows)
        self.assertEqual(artifact["quality_gate"], "failed")
        self.assertEqual(recommend(profile(), [club()], artifact)[0]["method"], "baseline")

    def test_no_cold_club_evidence_blocks_publication(self):
        rows = synthetic_outcomes()
        for row in rows:
            if row["club_id"].startswith("new-"):
                row["club_id"] = row["club_id"].replace("new-", "")
        artifact = train_model(rows)
        self.assertEqual(artifact["evaluation"]["new_club"]["rows"], 0)
        self.assertEqual(artifact["quality_gate"], "failed")

    def test_invalid_outcomes_rejected(self):
        for change in ({"carry_yards": float("nan")}, {"carry_yards": 401},
                       {"shot_count": 4}, {"shot_count": 501},
                       {"measured_at": "2020-01-01"}, {"club": None}, {"id": None}):
            rows = synthetic_outcomes()
            rows[0].update(change)
            with self.assertRaises(ValueError):
                train_model(rows)

    def test_json_model_loading_and_schema_validation(self):
        artifact = train_model(synthetic_outcomes())
        with patch.object(Path, "open", side_effect=FileNotFoundError):
            self.assertIsNone(load_model("missing.json"))
        from io import StringIO
        with patch.object(Path, "open", return_value=StringIO(json.dumps(artifact))), \
                patch.object(Path, "stat") as stat:
            stat.return_value.st_size = 100
            self.assertEqual(load_model("local.json")["version"], 1)
        for change in ({"feature_names": ["club_id"]}, {"intercept": float("inf")},
                       {"coefficients": [0]}, {"residual_mae": -1}, {"outcome_ids": []},
                       {"outcome_ids": ["1"]}):
            invalid = dict(artifact, **change)
            with self.assertRaises(ValueError):
                recommend(profile(), [club()], invalid)

        invalid = copy.deepcopy(artifact)
        invalid["evaluation"]["counts"]["overlapping_golfers"] = 1
        with self.assertRaises(ValueError):
            recommend(profile(), [club()], invalid)

    def test_cli_insufficient_data_and_failed_gate_never_save(self):
        from scripts import train_recommender
        with patch.object(train_recommender, "load_outcomes", return_value=[]), \
                patch.object(train_recommender, "save_model") as save, \
                patch("sys.stderr"):
            self.assertEqual(train_recommender.main(["--output", "unused.json"]), 2)
            save.assert_not_called()
        artifact = train_model(synthetic_outcomes())
        artifact["quality_gate"] = "failed"
        with patch.object(train_recommender, "load_outcomes", return_value=[]), \
                patch.object(train_recommender, "train_model", return_value=artifact), \
                patch.object(train_recommender, "save_model") as save, \
                patch("sys.stderr"):
            self.assertEqual(train_recommender.main(["--output", "unused.json"]), 2)
            save.assert_not_called()

    def test_atomic_json_save_roundtrip(self):
        from scripts.train_recommender import save_model
        import uuid
        path = Path("tests") / ("recommender-test-" + uuid.uuid4().hex + ".json")
        try:
            artifact = train_model(synthetic_outcomes())
            save_model(artifact, path)
            self.assertEqual(load_model(path), artifact)
            self.assertEqual(list(path.parent.glob("." + path.name + ".*.pending")), [])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
