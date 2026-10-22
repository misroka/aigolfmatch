"""Conservative validation shared by ingestion entry points."""

import math
from datetime import datetime
from urllib.parse import urlparse


SPEC_RANGES = {
    "loft_degrees": (0, 90),
    "lie_angle_degrees": (0, 90),
    "club_length_inches": (20, 60),
    "club_head_volume_cc": (1, 500),
    "offset_mm": (0, 30),
    "bounce_degrees": (-10, 30),
}
SPEC_TEXT = (
    "swing_weight", "shaft_material", "shaft_flex", "shaft_model",
    "grip_model", "club_head_material",
)


def handedness(value):
    """Unknown source values must not imply compatibility with either hand."""
    if not isinstance(value, str):
        return None
    return {"right": "Right", "left": "Left", "both": "Both"}.get(value.strip().lower())


def skill_level(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().title()
    return normalized if normalized in ("Beginner", "Intermediate", "Advanced", "Professional") else None


def number(value, minimum=0, maximum=99999999.99):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numeric measurement")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError("Measurement outside supported range")
    return result


def release_year(value):
    if value is None or value == "":
        return None
    result = number(value, 1800, datetime.now().year + 1)
    if not result.is_integer():
        raise ValueError("Release year must be an integer")
    return int(result)


def source_url(value):
    if not isinstance(value, str):
        raise ValueError("A product URL is required")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Product URL must use HTTP(S)")
    return value


def stock(value):
    if value is not None and not isinstance(value, bool):
        raise ValueError("Availability must be true, false or unknown")
    return value


def specifications(specs):
    """Return each explicit loft variant, never an arbitrary first loft."""
    if not isinstance(specs, dict):
        raise ValueError("Specifications must be an object")
    normalized = {}
    for key, bounds in SPEC_RANGES.items():
        if specs.get(key) is not None:
            normalized[key] = number(specs[key], *bounds)
            if key == "club_head_volume_cc" and not normalized[key].is_integer():
                raise ValueError("Head volume must be an integer")
    for key in SPEC_TEXT:
        if specs.get(key) is not None:
            value = specs[key]
            max_length = {"swing_weight": 10, "shaft_material": 50, "shaft_flex": 20}.get(key, 100)
            if not isinstance(value, str) or not value.strip() or len(value) > max_length:
                raise ValueError(f"Invalid specification: {key}")
            normalized[key] = value.strip()
    lofts = specs.get("lofts")
    if lofts is not None:
        if not isinstance(lofts, list) or not lofts:
            raise ValueError("Lofts must be a nonempty list")
        lofts = list(dict.fromkeys(number(loft, 0, 90) for loft in lofts))
        if None in lofts:
            raise ValueError("Loft cannot be unknown inside a loft list")
        if "loft_degrees" in normalized and lofts != [normalized["loft_degrees"]]:
            raise ValueError("Conflicting loft specifications")
        return [dict(normalized, loft_degrees=loft) for loft in lofts]
    return [normalized] if normalized else []


def refresh_current_price(cursor, club_id):
    """The cache must not outlive a fresh, explicitly available offer."""
    cursor.execute(
        """
        UPDATE golf_clubs SET (current_price, price_updated_at) = (
            SELECT price, price_checked_at FROM product_sources
            WHERE golf_club_id = %s AND in_stock IS TRUE
              AND price BETWEEN 0 AND 99999999.99
              AND price_checked_at >= CURRENT_TIMESTAMP - INTERVAL '1 day'
              AND price_checked_at <= CURRENT_TIMESTAMP
            ORDER BY price ASC, price_checked_at DESC LIMIT 1
        ), updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (club_id, club_id),
    )
