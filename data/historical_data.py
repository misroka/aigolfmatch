"""Historical golf club data for major releases (2015-2025)."""

import json
from pathlib import Path

# This is a starting point - expand with comprehensive data
HISTORICAL_CLUBS = [
    # TaylorMade Drivers
    {
        "brand": "TaylorMade",
        "model": "Stealth 2 Plus Driver",
        "year": 2023,
        "club_type": "Driver",
        "msrp": 599.99,
        "skill_level": "Advanced",
        "description": "Carbon face with 60X Carbon Twist Face technology",
        "specs": {
            "lofts": [8, 9, 10.5],
            "shaft_options": ["Fujikura Ventus TR Red", "Mitsubishi Tensei AV Raw Blue"],
            "adjustable": True
        }
    },
    {
        "brand": "TaylorMade",
        "model": "Stealth Driver",
        "year": 2022,
        "club_type": "Driver",
        "msrp": 579.99,
        "skill_level": "Intermediate",
        "description": "First carbon face driver from TaylorMade"
    },
    {
        "brand": "TaylorMade",
        "model": "SIM2 Max Driver",
        "year": 2021,
        "club_type": "Driver",
        "msrp": 529.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "TaylorMade",
        "model": "SIM Max Driver",
        "year": 2020,
        "club_type": "Driver",
        "msrp": 499.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "TaylorMade",
        "model": "M6 Driver",
        "year": 2019,
        "club_type": "Driver",
        "msrp": 499.99,
        "skill_level": "Beginner"
    },
    
    # Callaway Drivers
    {
        "brand": "Callaway",
        "model": "Paradym Ai Smoke Max Driver",
        "year": 2024,
        "club_type": "Driver",
        "msrp": 599.99,
        "skill_level": "Intermediate",
        "description": "AI-designed face with carbon chassis"
    },
    {
        "brand": "Callaway",
        "model": "Paradym Driver",
        "year": 2023,
        "club_type": "Driver",
        "msrp": 579.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "Callaway",
        "model": "Rogue ST Max Driver",
        "year": 2022,
        "club_type": "Driver",
        "msrp": 549.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "Callaway",
        "model": "Epic Speed Driver",
        "year": 2021,
        "club_type": "Driver",
        "msrp": 529.99,
        "skill_level": "Advanced"
    },
    
    # Titleist Drivers
    {
        "brand": "Titleist",
        "model": "TSR3 Driver",
        "year": 2023,
        "club_type": "Driver",
        "msrp": 599.99,
        "skill_level": "Advanced",
        "description": "Low-spin driver for skilled players"
    },
    {
        "brand": "Titleist",
        "model": "TSi3 Driver",
        "year": 2021,
        "club_type": "Driver",
        "msrp": 549.99,
        "skill_level": "Advanced"
    },
    {
        "brand": "Titleist",
        "model": "TS3 Driver",
        "year": 2019,
        "club_type": "Driver",
        "msrp": 519.99,
        "skill_level": "Advanced"
    },
    
    # Ping Drivers
    {
        "brand": "Ping",
        "model": "G430 Max Driver",
        "year": 2023,
        "club_type": "Driver",
        "msrp": 599.99,
        "skill_level": "Intermediate",
        "description": "High MOI with Carbonfly Wrap"
    },
    {
        "brand": "Ping",
        "model": "G425 Max Driver",
        "year": 2021,
        "club_type": "Driver",
        "msrp": 539.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "Ping",
        "model": "G410 Plus Driver",
        "year": 2019,
        "club_type": "Driver",
        "msrp": 499.99,
        "skill_level": "Intermediate"
    },
    
    # TaylorMade Irons
    {
        "brand": "TaylorMade",
        "model": "P790 Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1599.99,
        "skill_level": "Intermediate",
        "description": "Hollow body distance irons with forged face"
    },
    {
        "brand": "TaylorMade",
        "model": "Stealth Irons",
        "year": 2022,
        "club_type": "Iron Set",
        "msrp": 1199.99,
        "skill_level": "Beginner"
    },
    {
        "brand": "TaylorMade",
        "model": "P7MC Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1399.99,
        "skill_level": "Advanced",
        "description": "Compact muscle cavity for tour players"
    },
    
    # Callaway Irons
    {
        "brand": "Callaway",
        "model": "Paradym Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1399.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "Callaway",
        "model": "Apex Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1499.99,
        "skill_level": "Intermediate",
        "description": "AI-designed Flash Face Cup"
    },
    {
        "brand": "Callaway",
        "model": "Rogue ST Max Irons",
        "year": 2022,
        "club_type": "Iron Set",
        "msrp": 1199.99,
        "skill_level": "Beginner"
    },
    
    # Titleist Irons
    {
        "brand": "Titleist",
        "model": "T200 Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1599.99,
        "skill_level": "Intermediate",
        "description": "Distance irons with tungsten weighting"
    },
    {
        "brand": "Titleist",
        "model": "T100 Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1599.99,
        "skill_level": "Advanced",
        "description": "Tour-level precision irons"
    },
    {
        "brand": "Titleist",
        "model": "T300 Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1499.99,
        "skill_level": "Beginner",
        "description": "Maximum distance and forgiveness"
    },
    
    # Mizuno Irons
    {
        "brand": "Mizuno",
        "model": "JPX923 Hot Metal Irons",
        "year": 2023,
        "club_type": "Iron Set",
        "msrp": 1199.99,
        "skill_level": "Intermediate",
        "description": "High ball speed with Chromoly 4335"
    },
    {
        "brand": "Mizuno",
        "model": "JPX921 Forged Irons",
        "year": 2021,
        "club_type": "Iron Set",
        "msrp": 1099.99,
        "skill_level": "Intermediate"
    },
    
    # Putters
    {
        "brand": "Scotty Cameron",
        "model": "Phantom X 11.5",
        "year": 2023,
        "club_type": "Putter",
        "msrp": 449.99,
        "skill_level": "Advanced"
    },
    {
        "brand": "Odyssey",
        "model": "Tri-Hot 5K",
        "year": 2023,
        "club_type": "Putter",
        "msrp": 349.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "TaylorMade",
        "model": "Spider Tour X",
        "year": 2023,
        "club_type": "Putter",
        "msrp": 399.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "Ping",
        "model": "PLD Milled Anser",
        "year": 2023,
        "club_type": "Putter",
        "msrp": 499.99,
        "skill_level": "Advanced"
    },
    
    # Wedges
    {
        "brand": "Titleist",
        "model": "Vokey SM9",
        "year": 2023,
        "club_type": "Wedge",
        "msrp": 179.99,
        "skill_level": "Advanced",
        "description": "Progressive CG for precise control"
    },
    {
        "brand": "Cleveland",
        "model": "RTX ZipCore",
        "year": 2023,
        "club_type": "Wedge",
        "msrp": 149.99,
        "skill_level": "Intermediate"
    },
    {
        "brand": "Callaway",
        "model": "Jaws Raw",
        "year": 2023,
        "club_type": "Wedge",
        "msrp": 159.99,
        "skill_level": "Advanced"
    }
]


def save_historical_data():
    """Save historical data to JSON file."""
    output_path = Path(__file__).parent.parent / 'data' / 'historical' / 'clubs_2015_2025.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(HISTORICAL_CLUBS, f, indent=2)
    
    print(f"Saved {len(HISTORICAL_CLUBS)} historical clubs to {output_path}")


if __name__ == "__main__":
    save_historical_data()
