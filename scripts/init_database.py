"""Initialize the database with brands and club types."""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db


def load_brands():
    """Load brands from config file into database."""
    config_path = Path(__file__).parent.parent / 'config' / 'brands.json'
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    brands_loaded = 0
    
    with db.get_cursor() as cursor:
        for brand in data['major_brands']:
            try:
                cursor.execute(
                    """
                    INSERT INTO brands (name, country, website)
                    VALUES (%(name)s, %(country)s, %(website)s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    brand
                )
                brands_loaded += 1
            except Exception as e:
                print(f"Error loading brand {brand['name']}: {str(e)}")
    
    print(f"Loaded {brands_loaded} brands")


def load_club_types():
    """Load club types into database."""
    club_types = [
        {'name': 'Driver', 'description': 'Longest club for tee shots'},
        {'name': 'Fairway Wood', 'description': 'Woods for fairway and tee shots'},
        {'name': 'Hybrid', 'description': 'Cross between wood and iron'},
        {'name': 'Iron', 'description': 'Precision clubs for approach shots'},
        {'name': 'Wedge', 'description': 'High-loft clubs for short game'},
        {'name': 'Putter', 'description': 'Club for putting on the green'},
        {'name': 'Iron Set', 'description': 'Complete set of irons'},
        {'name': 'Complete Set', 'description': 'Full set of clubs for beginners'}
    ]
    
    types_loaded = 0
    
    with db.get_cursor() as cursor:
        for club_type in club_types:
            try:
                cursor.execute(
                    """
                    INSERT INTO club_types (name, description)
                    VALUES (%(name)s, %(description)s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    club_type
                )
                types_loaded += 1
            except Exception as e:
                print(f"Error loading club type {club_type['name']}: {str(e)}")
    
    print(f"Loaded {types_loaded} club types")


def load_sample_technologies():
    """Load some common golf club technologies."""
    technologies = [
        {'name': 'Carbon Face', 'description': 'Carbon fiber face for increased ball speed'},
        {'name': 'AI Design', 'description': 'AI-optimized face and weight distribution'},
        {'name': 'Adjustable Hosel', 'description': 'Adjustable loft and lie angle'},
        {'name': 'Multi-Material', 'description': 'Multiple materials for optimized performance'},
        {'name': 'Speed Frame', 'description': 'Reinforced frame for stability'},
        {'name': 'Tungsten Weighting', 'description': 'Tungsten weights for MOI optimization'},
        {'name': 'Jailbreak', 'description': 'Internal bars for energy transfer'},
        {'name': 'Flash Face', 'description': 'AI-designed variable thickness face'},
        {'name': 'Twist Face', 'description': 'Curved face for straighter mis-hits'},
        {'name': 'Speed Pocket', 'description': 'Slot for increased low-face flexibility'},
        {'name': 'Forged Construction', 'description': 'Forged for better feel'},
        {'name': 'Hollow Body', 'description': 'Hollow construction for forgiveness'},
        {'name': 'COR-Eye', 'description': 'Suspended face for increased ball speed'},
        {'name': 'V-Steel', 'description': 'V-shaped sole for versatility'}
    ]
    
    techs_loaded = 0
    
    with db.get_cursor() as cursor:
        for tech in technologies:
            try:
                cursor.execute(
                    """
                    INSERT INTO technologies (name, description)
                    VALUES (%(name)s, %(description)s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    tech
                )
                techs_loaded += 1
            except Exception as e:
                print(f"Error loading technology {tech['name']}: {str(e)}")
    
    print(f"Loaded {techs_loaded} technologies")


def main():
    """Initialize database with reference data."""
    print("Initializing golf club database...")
    
    try:
        load_brands()
        load_club_types()
        load_sample_technologies()
        
        print("\n✓ Database initialization complete!")
        print("\nNext steps:")
        print("1. Run scrapers to collect club data: python scripts/scrape_retailers.py")
        print("2. Load historical data: python scripts/load_historical_data.py")
        
    except Exception as e:
        print(f"\n✗ Error initializing database: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
