"""Data models for golf clubs."""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


@dataclass
class Brand:
    """Golf club brand."""
    id: Optional[int] = None
    name: str = ""
    country: Optional[str] = None
    website: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ClubType:
    """Type of golf club."""
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None


@dataclass
class ClubSpecification:
    """Technical specifications for a golf club."""
    id: Optional[int] = None
    golf_club_id: Optional[int] = None
    loft_degrees: Optional[Decimal] = None
    lie_angle_degrees: Optional[Decimal] = None
    club_length_inches: Optional[Decimal] = None
    swing_weight: Optional[str] = None
    shaft_material: Optional[str] = None
    shaft_flex: Optional[str] = None
    shaft_model: Optional[str] = None
    grip_model: Optional[str] = None
    club_head_material: Optional[str] = None
    club_head_volume_cc: Optional[int] = None
    offset_mm: Optional[Decimal] = None
    bounce_degrees: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class GolfClub:
    """Golf club model."""
    id: Optional[int] = None
    brand_id: Optional[int] = None
    club_type_id: Optional[int] = None
    model_name: str = ""
    year_released: int = 2025
    year_discontinued: Optional[int] = None
    msrp: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    is_current: bool = True
    description: Optional[str] = None
    target_handicap_range: Optional[str] = None
    skill_level: Optional[str] = None
    gender: Optional[str] = None
    hand: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Related data (not in DB directly)
    brand_name: Optional[str] = None
    club_type_name: Optional[str] = None
    specifications: Optional[ClubSpecification] = None
    
    def __str__(self):
        return f"{self.brand_name} {self.model_name} ({self.year_released})"


@dataclass
class ProductSource:
    """Product availability and pricing from retailers."""
    id: Optional[int] = None
    golf_club_id: Optional[int] = None
    source_name: str = ""
    product_url: Optional[str] = None
    price: Optional[Decimal] = None
    in_stock: Optional[bool] = None
    last_checked: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class ClubReview:
    """Aggregated reviews and ratings."""
    id: Optional[int] = None
    golf_club_id: Optional[int] = None
    reviewer_profile_id: Optional[int] = None
    source_name: Optional[str] = None
    rating: Optional[Decimal] = None
    num_reviews: Optional[int] = None
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    review_text: Optional[str] = None
    review_title: Optional[str] = None
    verified_purchase: Optional[bool] = None
    helpful_count: Optional[int] = None
    review_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class ReviewerProfile:
    """Reviewer profile for personalized recommendations."""
    id: Optional[int] = None
    external_id: Optional[str] = None
    source_name: Optional[str] = None
    age: Optional[int] = None
    weight_lbs: Optional[int] = None
    height_inches: Optional[int] = None
    gender: Optional[str] = None
    handicap: Optional[Decimal] = None
    average_drive_distance_yards: Optional[int] = None
    swing_speed_mph: Optional[int] = None
    swing_tempo: Optional[str] = None
    ball_flight: Optional[str] = None
    skill_level: Optional[str] = None
    years_playing: Optional[int] = None
    rounds_per_year: Optional[int] = None
    primary_miss: Optional[str] = None
    launch_angle_preference: Optional[str] = None
    spin_preference: Optional[str] = None
    feel_preference: Optional[str] = None
    game_improvement_priority: Optional[str] = None
    budget_range: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Technology:
    """Club technology or feature."""
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None


@dataclass
class ScrapingLog:
    """Log entry for scraping activity."""
    id: Optional[int] = None
    source_name: str = ""
    scrape_type: Optional[str] = None
    status: str = "pending"
    records_added: int = 0
    records_updated: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
