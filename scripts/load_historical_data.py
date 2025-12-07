"""Load historical golf club data into the database."""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db, log_scrape


def get_or_create_brand_id(brand_name: str) -> int:
    """Get brand ID or create if doesn't exist."""
    with db.get_cursor() as cursor:
        cursor.execute("SELECT id FROM brands WHERE name ILIKE %s", (brand_name,))
        result = cursor.fetchone()
        
        if result:
            return result['id']
        
        cursor.execute(
            "INSERT INTO brands (name) VALUES (%s) RETURNING id",
            (brand_name,)
        )
        return cursor.fetchone()['id']


def get_club_type_id(club_type: str) -> int:
    """Get club type ID."""
    with db.get_cursor() as cursor:
        cursor.execute("SELECT id FROM club_types WHERE name = %s", (club_type,))
        result = cursor.fetchone()
        
        if not result:
            # Create if doesn't exist
            cursor.execute(
                "INSERT INTO club_types (name) VALUES (%s) RETURNING id",
                (club_type,)
            )
            result = cursor.fetchone()
        
        return result['id']


def load_historical_clubs(clubs_data: list, years: int = 10):
    """
    Load historical clubs into the database.
    
    Args:
        clubs_data: List of club dictionaries
        years: Number of years back to load (default 10)
    """
    current_year = datetime.now().year
    min_year = current_year - years
    
    added = 0
    skipped = 0
    
    for club in clubs_data:
        # Filter by year range
        if club.get('year', current_year) < min_year:
            skipped += 1
            continue
        
        try:
            brand_id = get_or_create_brand_id(club['brand'])
            club_type_id = get_club_type_id(club['club_type'])
            
            # Check if club already exists
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM golf_clubs 
                    WHERE brand_id = %s AND model_name = %s AND year_released = %s
                    """,
                    (brand_id, club['model'], club['year'])
                )
                existing = cursor.fetchone()
            
            if existing:
                print(f"Skipping existing: {club['brand']} {club['model']} ({club['year']})")
                skipped += 1
                continue
            
            # Determine if club is current (released in last 2 years)
            is_current = club['year'] >= (current_year - 2)
            
            # Insert club
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO golf_clubs (
                        brand_id, club_type_id, model_name, year_released,
                        msrp, is_current, description, skill_level
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        brand_id,
                        club_type_id,
                        club['model'],
                        club['year'],
                        club.get('msrp'),
                        is_current,
                        club.get('description'),
                        club.get('skill_level')
                    )
                )
                club_id = cursor.fetchone()['id']
            
            # Insert specifications if available
            if 'specs' in club:
                specs = club['specs']
                with db.get_cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO club_specifications (
                            golf_club_id, loft_degrees, shaft_material
                        ) VALUES (%s, %s, %s)
                        """,
                        (
                            club_id,
                            specs.get('lofts', [None])[0] if isinstance(specs.get('lofts'), list) else None,
                            specs.get('shaft_material')
                        )
                    )
            
            print(f"Added: {club['brand']} {club['model']} ({club['year']})")
            added += 1
        
        except Exception as e:
            print(f"Error loading {club.get('brand')} {club.get('model')}: {str(e)}")
            continue
    
    return added, skipped


def main():
    """Load historical data from files."""
    parser = argparse.ArgumentParser(description='Load historical golf club data')
    parser.add_argument('--years', type=int, default=10,
                       help='Number of years back to load (default: 10)')
    parser.add_argument('--file', type=str,
                       help='Specific JSON file to load')
    
    args = parser.parse_args()
    
    print(f"Loading historical golf club data (past {args.years} years)...")
    
    try:
        if args.file:
            # Load specific file
            file_path = Path(args.file)
            with open(file_path, 'r') as f:
                clubs_data = json.load(f)
        else:
            # Generate and load default historical data
            data_dir = Path(__file__).parent.parent / 'data'
            historical_file = data_dir / 'historical' / 'clubs_2015_2025.json'
            
            if not historical_file.exists():
                print("Generating historical data...")
                from data.historical_data import HISTORICAL_CLUBS, save_historical_data
                save_historical_data()
                clubs_data = HISTORICAL_CLUBS
            else:
                with open(historical_file, 'r') as f:
                    clubs_data = json.load(f)
        
        added, skipped = load_historical_clubs(clubs_data, args.years)
        
        print(f"\n✓ Historical data load complete!")
        print(f"  Added: {added}")
        print(f"  Skipped: {skipped}")
        
        log_scrape(
            source_name="Historical Data",
            scrape_type=f"historical_{args.years}y",
            status="success",
            records_added=added,
            records_updated=0
        )
    
    except Exception as e:
        print(f"\n✗ Error loading historical data: {str(e)}")
        log_scrape(
            source_name="Historical Data",
            scrape_type="historical",
            status="failed",
            error_message=str(e)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
