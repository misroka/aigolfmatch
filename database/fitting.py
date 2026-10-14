"""Consented, measured fitting outcomes, independent of scraped reviews."""

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg2.extras import Json

from database.db import db


CLUB_TYPES = ("Driver", "Fairway Wood", "Hybrid", "Iron", "Wedge", "Putter")
SKILL_LEVELS = ("Beginner", "Intermediate", "Advanced", "Professional")
CONSENT_VERSION = "fitting-outcomes-v1"


def _number(payload, name, minimum=None, maximum=None, *, positive=False,
            integer=False):
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"{name} must be a finite number") from None
    if (not math.isfinite(number)
            or (positive and number <= 0)
            or (minimum is not None and number < minimum)
            or (maximum is not None and number > maximum)
            or (integer and not number.is_integer())):
        raise ValueError(f"{name} is outside its allowed range")
    return int(number) if integer else number


def _choice(payload, name, choices):
    value = payload.get(name)
    if value not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}")
    return value


def validate_profile(payload):
    """Return only validated fitting features; never retain submitted identity."""
    if not isinstance(payload, Mapping):
        raise ValueError("profile must be an object")
    profile = {
        "handicap": _number(payload, "handicap", 0, 54),
        "swing_speed_mph": _number(payload, "swing_speed_mph", 30, 150),
        "budget": _number(payload, "budget", positive=True),
        "hand": _choice(payload, "hand", ("Right", "Left")),
        "club_type": _choice(payload, "club_type", CLUB_TYPES),
        "skill_level": _choice(payload, "skill_level", SKILL_LEVELS),
    }
    if payload.get("loft_degrees") not in (None, ""):
        profile["loft_degrees"] = _number(payload, "loft_degrees", 0, 70)
    return profile


def _golfer_id(value):
    try:
        if not isinstance(value, (str, UUID)):
            raise ValueError()
        result = UUID(str(value))
        if result.version != 4:
            raise ValueError()
    except (ValueError, AttributeError, TypeError):
        raise ValueError("golfer_id must be a pseudonymous session UUID4") from None
    return str(result)


def validate_outcome(payload):
    """Validate measured data. The caller must supply its server-side session ID."""
    if not isinstance(payload, Mapping):
        raise ValueError("outcome must be an object")
    if payload.get("consent") is not True:
        raise ValueError("explicit consent is required")
    measured_at = payload.get("measured_at")
    if isinstance(measured_at, str):
        try:
            measured_at = datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("measured_at must be an ISO8601 UTC timestamp") from None
    if (not isinstance(measured_at, datetime) or measured_at.tzinfo is None
            or measured_at.utcoffset() is None):
        raise ValueError("measured_at must include a UTC offset")
    try:
        measured_at = measured_at.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise ValueError("measured_at is outside the supported UTC range") from None
    if measured_at > datetime.now(timezone.utc):
        raise ValueError("measured_at must not be in the future")
    return {
        "consent": True,
        "golfer_id": _golfer_id(payload.get("golfer_id")),
        "golf_club_id": _number(payload, "golf_club_id", 1, 2147483647, integer=True),
        "carry_yards": _number(payload, "carry_yards", 0, 400),
        "dispersion_yards": _number(payload, "dispersion_yards", 0, 150),
        "shot_count": _number(payload, "shot_count", 5, 500, integer=True),
        "profile": validate_profile(payload.get("profile")),
        "measured_at": measured_at,
    }


# Each lateral join picks exactly one record; unknown offer fields stay NULL.
_CANDIDATE_SELECT = """
    SELECT gc.id, b.name AS brand_name, gc.model_name,
           ct.name AS club_type_name, gc.hand, gc.skill_level,
           cs.loft_degrees, cs.shaft_flex,
           ps.price, ps.price_checked_at,
           ps.in_stock, ps.source_name, ps.product_url
    FROM golf_clubs gc
    JOIN brands b ON b.id = gc.brand_id
    JOIN club_types ct ON ct.id = gc.club_type_id
    LEFT JOIN LATERAL (
        SELECT loft_degrees, shaft_flex FROM club_specifications
        WHERE golf_club_id = gc.id AND validated IS TRUE
        ORDER BY updated_at DESC NULLS LAST, id DESC LIMIT 1
    ) cs ON TRUE
    LEFT JOIN LATERAL (
        SELECT price, price_checked_at, in_stock, source_name, product_url
        FROM product_sources WHERE golf_club_id = gc.id
        ORDER BY price_checked_at DESC NULLS LAST, id DESC LIMIT 1
    ) ps ON TRUE
"""


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def get_recommendation_candidates(club_type):
    """Return actual catalog specifications and latest observed offers."""
    _choice({"club_type": club_type}, "club_type", CLUB_TYPES)
    with db.get_cursor() as cursor:
        cursor.execute(
            _CANDIDATE_SELECT
            + " WHERE gc.specs_validated IS TRUE AND ct.name = %s ORDER BY gc.id",
            (club_type,),
        )
        return [_plain(row) for row in cursor.fetchall()]


def save_fitting_outcome(data):
    """Validate and atomically store collection-time catalog features and consent."""
    outcome = validate_outcome(data)
    with db.get_cursor() as cursor:
        cursor.execute(
            _CANDIDATE_SELECT
            + " WHERE gc.specs_validated IS TRUE AND gc.id = %s FOR SHARE OF gc",
            (outcome["golf_club_id"],),
        )
        club = cursor.fetchone()
        if club is None:
            raise ValueError("golf_club_id does not exist")
        profile = outcome["profile"]
        if (club["club_type_name"] != profile["club_type"]
                or club["hand"] not in (profile["hand"], "Both")):
            raise ValueError("club is incompatible with this profile")
        cursor.execute("""
            INSERT INTO fitting_outcomes (
                golfer_id, golf_club_id, profile, club_snapshot,
                carry_yards, dispersion_yards, shot_count, measured_at,
                consent, consented_at, consent_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                      TRUE, CURRENT_TIMESTAMP, %s)
            RETURNING id
        """, (
            outcome["golfer_id"], outcome["golf_club_id"],
            Json(profile), Json(_plain(club)),
            outcome["carry_yards"], outcome["dispersion_yards"],
            outcome["shot_count"], outcome["measured_at"], CONSENT_VERSION,
        ))
        return cursor.fetchone()["id"]


def get_training_outcomes():
    """Read only consented measurements, without joining mutable catalog data."""
    with db.get_cursor() as cursor:
        cursor.execute("""
            SELECT id, profile, club_snapshot AS club, golfer_id::text AS golfer_id,
                   golf_club_id AS club_id, measured_at,
                   carry_yards, dispersion_yards, shot_count
            FROM fitting_outcomes
            WHERE consent IS TRUE AND consented_at IS NOT NULL
                  AND consent_version = %s
            ORDER BY measured_at, id
        """, (CONSENT_VERSION,))
        return [_plain(row) for row in cursor.fetchall()]


def is_model_current(model):
    """Fail closed if any training/evaluation outcome has lost its consent."""
    if not isinstance(model, Mapping):
        return False
    outcome_ids = model.get("outcome_ids")
    if (not isinstance(outcome_ids, list) or not outcome_ids
            or any(type(outcome_id) is not int
                   or not 1 <= outcome_id <= 9223372036854775807
                   for outcome_id in outcome_ids)
            or len(set(outcome_ids)) != len(outcome_ids)):
        return False
    try:
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS consented_count
                FROM fitting_outcomes
                WHERE id = ANY(%s) AND consent IS TRUE
                      AND consented_at IS NOT NULL AND consent_version = %s
            """, (outcome_ids, CONSENT_VERSION))
            return cursor.fetchone()["consented_count"] == len(outcome_ids)
    except Exception:
        return False


def delete_fitting_outcomes(golfer_id):
    """Permanently remove a session's measurements when consent is withdrawn."""
    golfer_id = _golfer_id(golfer_id)
    with db.get_cursor() as cursor:
        cursor.execute("DELETE FROM fitting_outcomes WHERE golfer_id = %s",
                       (golfer_id,))
        return cursor.rowcount


def get_recommendation_health():
    """Expose aggregate readiness/freshness only, never golfer identifiers."""
    health = {
        "database_available": False,
        "candidate_count": 0,
        "outcome_count": 0,
        "latest_outcome_at": None,
        "latest_price_checked_at": None,
    }
    try:
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT (SELECT COUNT(*) FROM golf_clubs
                        WHERE specs_validated IS TRUE) AS candidate_count,
                       COUNT(*) AS outcome_count,
                       MAX(measured_at) AS latest_outcome_at,
                       (SELECT MAX(price_checked_at) FROM product_sources)
                           AS latest_price_checked_at
                FROM fitting_outcomes
                WHERE consent IS TRUE AND consented_at IS NOT NULL
                      AND consent_version = %s
            """, (CONSENT_VERSION,))
            health.update(_plain(cursor.fetchone()))
        health["database_available"] = True
    except Exception:
        # Monitoring must remain usable during an outage without exposing DB errors.
        pass
    return health
