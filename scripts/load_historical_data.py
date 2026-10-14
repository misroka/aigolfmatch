"""Load historical golf club data into the database."""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db, log_scrape
from database.validation import number, release_year, specifications, SPEC_RANGES, SPEC_TEXT
from psycopg2.extras import Json


def get_or_create_brand_id(brand_name: str, cursor=None) -> int:
    """Get brand ID or create if doesn't exist."""
    if cursor is None:
        with db.get_cursor() as own_cursor:
            return get_or_create_brand_id(brand_name, own_cursor)
    else:
        cursor.execute("SELECT id FROM brands WHERE LOWER(name) = LOWER(%s)", (brand_name,))
        result = cursor.fetchone()
        
        if result:
            return result['id']
        
        cursor.execute(
            "INSERT INTO brands (name) VALUES (%s) RETURNING id",
            (brand_name,)
        )
        return cursor.fetchone()['id']


def get_club_type_id(club_type: str, cursor=None) -> int:
    """Get club type ID."""
    if cursor is None:
        with db.get_cursor() as own_cursor:
            return get_club_type_id(club_type, own_cursor)
    else:
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


def load_historical_clubs(clubs_data: list, years: int = 10,
                          source_name="Historical Data", source_url=None):
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
    
    with db.get_cursor() as cursor:
        for club in clubs_data:
            try:
                year = release_year(club.get('year'))
                if year is None or year < min_year:
                    skipped += 1
                    continue
                for key in ('brand', 'model', 'club_type'):
                    if not isinstance(club.get(key), str) or not club[key].strip():
                        raise ValueError(f"Missing {key}")
                msrp = number(club.get('msrp'))
                variants = specifications(club.get('specs', {}))
                provenance = club.get('source_name') or club.get('source') or source_name
                provenance_url = club.get('source_url') or source_url
                if not isinstance(provenance, str) or not provenance.strip():
                    raise ValueError("Source name is required")
            except (ValueError, TypeError) as exc:
                print(f"Skipping invalid historical club: {exc}")
                skipped += 1
                continue
            brand_id = get_or_create_brand_id(club['brand'], cursor)
            club_type_id = get_club_type_id(club['club_type'], cursor)
            cursor.execute(
                """SELECT id FROM golf_clubs
                   WHERE brand_id = %s AND model_name = %s AND year_released = %s""",
                (brand_id, club['model'], year),
            )
            existing = cursor.fetchone()
            if existing:
                club_id = existing['id']
                cursor.execute(
                    """UPDATE golf_clubs SET source_name = COALESCE(source_name, %s),
                       source_url = COALESCE(source_url, %s),
                       specs_validated = specs_validated OR %s WHERE id = %s""",
                    (provenance, provenance_url, bool(variants), club_id),
                )
                skipped += 1
            else:
                cursor.execute(
                    """INSERT INTO golf_clubs
                       (brand_id, club_type_id, model_name, year_released, msrp,
                        is_current, description, skill_level, source_name, source_url, specs_validated)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (brand_id, club_type_id, club['model'], year, msrp, year >= current_year - 2,
                     club.get('description'), club.get('skill_level'), provenance, provenance_url,
                     bool(variants)),
                )
                club_id = cursor.fetchone()['id']
                added += 1
            if variants:
                cursor.execute(
                    "DELETE FROM club_specifications WHERE golf_club_id = %s AND source_name = %s",
                    (club_id, provenance),
                )
            fields = list(SPEC_RANGES) + list(SPEC_TEXT)
            for variant in variants:
                columns = ['golf_club_id'] + fields + ['source_name', 'source_url', 'validated', 'raw_specs']
                cursor.execute(
                    f"INSERT INTO club_specifications ({', '.join(columns)}) "
                    f"VALUES ({', '.join(['%s'] * len(columns))})",
                    [club_id] + [variant.get(field) for field in fields]
                    + [provenance, provenance_url, True, Json(club.get('specs', {}))],
                )
    
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
        
        provenance_path = file_path if args.file else historical_file
        added, skipped = load_historical_clubs(
            clubs_data, args.years, source_url=str(provenance_path.resolve()))
        
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
