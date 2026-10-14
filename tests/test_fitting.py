"""Validation and transaction tests without a running PostgreSQL server."""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from database import fitting
from database.db import DatabaseConnection, get_club_by_id


def profile():
    return {
        "handicap": 18, "swing_speed_mph": 95, "budget": 500,
        "hand": "Right", "club_type": "Driver", "skill_level": "Intermediate",
    }


def outcome():
    return {
        "consent": True, "golfer_id": str(uuid4()), "golf_club_id": 7,
        "carry_yards": 230, "dispersion_yards": 20, "shot_count": 10,
        "profile": profile(),
        "measured_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    }


def club():
    return {
        "id": 7, "brand_name": "Example", "model_name": "Measured club",
        "club_type_name": "Driver", "hand": "Both", "skill_level": "Intermediate",
        "loft_degrees": Decimal("10.5"), "shaft_flex": "Regular",
        "price": None, "price_checked_at": None, "in_stock": None,
        "source_name": None, "product_url": None,
    }


class ValidationTests(unittest.TestCase):
    def test_profile_normalizes_form_numbers_and_drops_identity(self):
        data = profile()
        data.update(handicap="18.5", budget="499.99", loft_degrees="10.5",
                    email="not-retained@example.invalid")
        result = fitting.validate_profile(data)
        self.assertEqual(result["handicap"], 18.5)
        self.assertEqual(result["loft_degrees"], 10.5)
        self.assertNotIn("email", result)
        self.assertNotIn("loft_degrees", fitting.validate_profile(profile()))

    def test_profile_numeric_boundaries(self):
        for field, lower, upper in (
            ("handicap", 0, 54), ("swing_speed_mph", 30, 150),
            ("loft_degrees", 0, 70),
        ):
            for value in (lower, upper):
                with self.subTest(field=field, value=value):
                    self.assertEqual(
                        fitting.validate_profile({**profile(), field: value})[field],
                        value,
                    )
            for value in (lower - 0.1, upper + 0.1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        fitting.validate_profile({**profile(), field: value})

    def test_rejects_nonfinite_boolean_missing_and_invalid_numbers(self):
        for field in ("handicap", "swing_speed_mph", "budget", "loft_degrees"):
            for value in (True, False, float("nan"), float("inf"), "-Infinity",
                          Decimal("NaN"), "not numeric", [], {}):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        fitting.validate_profile({**profile(), field: value})
        for value in (0, -1):
            with self.assertRaises(ValueError):
                fitting.validate_profile({**profile(), "budget": value})
        for field in profile():
            data = profile()
            del data[field]
            with self.assertRaises(ValueError):
                fitting.validate_profile(data)

    def test_profile_choices_and_shape(self):
        for field, value in (("hand", "Both"), ("club_type", "Unknown"),
                             ("skill_level", "Expert")):
            with self.assertRaises(ValueError):
                fitting.validate_profile({**profile(), field: value})
        for payload in (None, [], "profile"):
            with self.assertRaises(ValueError):
                fitting.validate_profile(payload)

    def test_outcome_normalizes_time_and_drops_extra_fields(self):
        data = outcome()
        data.update(measured_at="2025-01-01T12:00:00+02:00", name="discard")
        validated = fitting.validate_outcome(data)
        self.assertEqual(validated["measured_at"],
                         datetime(2025, 1, 1, 10, tzinfo=timezone.utc))
        self.assertNotIn("name", validated)

    def test_requires_explicit_consent_and_pseudonymous_uuid(self):
        for consent in (False, None, 1, "true", "on"):
            with self.subTest(consent=consent):
                with self.assertRaises(ValueError):
                    fitting.validate_outcome({**outcome(), "consent": consent})
        for golfer in ("email@example.invalid", None, 123,
                       "00000000-0000-0000-0000-000000000000"):
            with self.subTest(golfer=golfer):
                with self.assertRaises(ValueError):
                    fitting.validate_outcome({**outcome(), "golfer_id": golfer})

    def test_outcome_numeric_constraints(self):
        invalid = {
            "golf_club_id": (0, -1, 1.5, True, 2147483648),
            "carry_yards": (-1, 401, True, float("nan"), float("inf")),
            "dispersion_yards": (-1, 151, False, "NaN"),
            "shot_count": (4, 501, 5.5, True),
        }
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        fitting.validate_outcome({**outcome(), field: value})
        for count in (5, 500):
            self.assertEqual(fitting.validate_outcome(
                {**outcome(), "shot_count": count})["shot_count"], count)

    def test_rejects_future_naive_invalid_missing_time_and_profile(self):
        for measured_at in (
            datetime.now(timezone.utc) + timedelta(days=1),
            datetime(2025, 1, 1), "2025-01-01", "bad", None,
            "9999-12-31T23:59:59-01:00",
        ):
            with self.subTest(measured_at=measured_at):
                with self.assertRaises(ValueError):
                    fitting.validate_outcome({**outcome(), "measured_at": measured_at})
        with self.assertRaises(ValueError):
            fitting.validate_outcome({**outcome(), "profile": {}})
        with self.assertRaises(ValueError):
            fitting.validate_outcome(None)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch("database.fitting.db.get_cursor")
        self.cursor_context = self.patch.start()
        self.addCleanup(self.patch.stop)
        self.cursor = self.cursor_context.return_value.__enter__.return_value

    def test_candidates_use_one_spec_and_cheapest_fresh_available_offer(self):
        self.cursor.fetchall.return_value = [club()]
        candidates = fitting.get_recommendation_candidates("Driver")
        self.assertEqual(candidates[0]["id"], 7)
        self.assertEqual(candidates[0]["loft_degrees"], 10.5)
        self.assertIsNone(candidates[0]["price"])
        self.assertIsNone(candidates[0]["in_stock"])
        query, params = self.cursor.execute.call_args.args
        self.assertEqual(params, ("Driver",))
        self.assertIn("updated_at DESC NULLS LAST, id DESC LIMIT 1", query)
        self.assertIn("price ASC, price_checked_at DESC, id DESC LIMIT 1", query)
        self.assertIn("ps.price_checked_at AS price_checked_at", query)
        self.assertIn("in_stock IS TRUE", query)
        self.assertIn("price BETWEEN 0 AND 99999999.99", query)
        self.assertIn("price_checked_at <= CURRENT_TIMESTAMP", query)
        self.assertIn(
            "price_checked_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'", query)
        self.assertIn("gc.specs_validated IS TRUE", query)
        self.assertIn("validated IS TRUE", query)
        self.assertNotIn("last_checked", query)
        self.assertNotIn("current_price", query)

    def test_invalid_club_type_does_not_query(self):
        with self.assertRaises(ValueError):
            fitting.get_recommendation_candidates("malicious query")
        self.cursor_context.assert_not_called()

    def test_atomic_save_uses_validated_profile_snapshot_and_server_consent(self):
        data = outcome()
        data["consent_version"] = "client cannot choose"
        self.cursor.fetchone.side_effect = [club(), {"id": 123}]
        self.assertEqual(fitting.save_fitting_outcome(data), 123)
        self.cursor_context.assert_called_once()
        select_query, select_params = self.cursor.execute.call_args_list[0].args
        self.assertIn("FOR SHARE OF gc", select_query)
        self.assertEqual(select_params, (7,))
        query, params = self.cursor.execute.call_args_list[1].args
        self.assertIn("CURRENT_TIMESTAMP", query)
        self.assertEqual(params[2].adapted, fitting.validate_profile(data["profile"]))
        self.assertEqual(params[3].adapted["id"], 7)
        self.assertEqual(params[3].adapted["loft_degrees"], 10.5)
        self.assertIsNone(params[3].adapted["price"])
        self.assertEqual(params[-1], fitting.CONSENT_VERSION)

    def test_invalid_save_never_opens_transaction(self):
        with self.assertRaises(ValueError):
            fitting.save_fitting_outcome({**outcome(), "consent": False})
        self.cursor_context.assert_not_called()

    def test_nonexistent_or_incompatible_club_is_not_saved(self):
        for candidate in (
            None, {**club(), "hand": "Left"},
            {**club(), "club_type_name": "Iron"},
        ):
            with self.subTest(candidate=candidate):
                self.cursor.reset_mock()
                self.cursor.fetchone.return_value = candidate
                with self.assertRaises(ValueError):
                    fitting.save_fitting_outcome(outcome())
                self.assertEqual(self.cursor.execute.call_count, 1)

    def test_training_uses_only_consented_snapshots_not_reviews_or_live_catalog(self):
        row = {
            "id": 19, "profile": profile(), "club": club(), "golfer_id": str(uuid4()),
            "club_id": 7, "carry_yards": 230, "dispersion_yards": 20,
            "shot_count": 10, "measured_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        self.cursor.fetchall.return_value = [row]
        result = fitting.get_training_outcomes()
        self.assertEqual(result[0]["id"], 19)
        self.assertEqual(result[0]["club"]["loft_degrees"], 10.5)
        query, params = self.cursor.execute.call_args.args
        self.assertIn("club_snapshot AS club", query)
        self.assertIn("consent IS TRUE", query)
        self.assertIn("consented_at IS NOT NULL", query)
        self.assertNotIn("JOIN", query)
        self.assertNotIn("review", query)
        self.assertEqual(params, (fitting.CONSENT_VERSION,))

    def test_model_requires_valid_nonempty_unique_outcome_manifest(self):
        for model in (
            None, {}, {"outcome_ids": []}, {"outcome_ids": "1"},
            {"outcome_ids": [True]}, {"outcome_ids": [1.0]},
            {"outcome_ids": [1, 1]}, {"outcome_ids": [0]},
            {"outcome_ids": [9223372036854775808]},
        ):
            with self.subTest(model=model):
                self.assertFalse(fitting.is_model_current(model))
        self.cursor_context.assert_not_called()

    def test_model_is_current_only_while_every_manifest_row_is_consented(self):
        model = {"outcome_ids": [11, 12, 13]}
        self.cursor.fetchone.return_value = {"consented_count": 3}
        self.assertTrue(fitting.is_model_current(model))
        query, params = self.cursor.execute.call_args.args
        self.assertIn("id = ANY(%s)", query)
        self.assertIn("consent IS TRUE", query)
        self.assertIn("consented_at IS NOT NULL", query)
        self.assertEqual(params, ([11, 12, 13], fitting.CONSENT_VERSION))
        self.cursor.fetchone.return_value = {"consented_count": 2}
        self.assertFalse(fitting.is_model_current(model))
        self.cursor.fetchone.return_value = {"consented_count": 0}
        self.assertFalse(fitting.is_model_current(model))
        self.assertEqual(self.cursor.execute.call_count, 3)

    def test_model_fails_closed_on_database_outage(self):
        self.cursor.execute.side_effect = RuntimeError("unavailable")
        self.assertFalse(fitting.is_model_current({"outcome_ids": [11]}))

    def test_withdrawal_deletes_only_session_records(self):
        golfer = str(uuid4())
        self.cursor.rowcount = 3
        self.assertEqual(fitting.delete_fitting_outcomes(golfer), 3)
        self.cursor.execute.assert_called_once_with(
            "DELETE FROM fitting_outcomes WHERE golfer_id = %s", (golfer,))

    def test_health_is_aggregate_and_tolerates_database_outage(self):
        self.cursor.fetchone.return_value = {
            "candidate_count": 2, "outcome_count": 3,
            "latest_outcome_at": None, "latest_price_checked_at": None,
        }
        health = fitting.get_recommendation_health()
        self.assertTrue(health["database_available"])
        self.assertEqual(health["outcome_count"], 3)
        query = self.cursor.execute.call_args.args[0]
        self.assertNotIn("golfer_id", query)
        self.cursor.execute.side_effect = RuntimeError("private connection details")
        health = fitting.get_recommendation_health()
        self.assertFalse(health["database_available"])
        self.assertNotIn("private", str(health))


class DatabaseTests(unittest.TestCase):
    @patch("database.db.db.get_cursor")
    def test_club_id_not_overwritten_by_specification(self, get_cursor):
        cursor = get_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"id": 7, "specification_id": 99}
        self.assertEqual(get_club_by_id(7)["id"], 7)
        query, params = cursor.execute.call_args.args
        self.assertNotIn("cs.*", query)
        self.assertIn("cs.id AS specification_id", query)
        self.assertIn("ORDER BY updated_at DESC NULLS LAST, id DESC", query)
        self.assertEqual(params, (7,))

    @patch("database.db.psycopg2.connect")
    def test_connection_rolls_back_failed_outcome_transaction(self, connect):
        connection = MagicMock()
        connect.return_value = connection
        with self.assertRaises(ValueError):
            with DatabaseConnection().get_connection():
                raise ValueError("failed insert")
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
