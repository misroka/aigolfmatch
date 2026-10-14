"""Conservative fitting-proxy recommendations, not evidence of causal efficacy.

Profiles require club_type, hand and a finite budget. Candidate offers require
price, explicitly True in_stock, and timezone-aware checked_at within 24 hours.
Missing or unrecognized hard constraints never count as matches.
"""

from .engine import FEATURE_NAMES, load_model, recommend
from .training import InsufficientDataError, train_model

__all__ = ["FEATURE_NAMES", "InsufficientDataError", "load_model", "recommend", "train_model"]
