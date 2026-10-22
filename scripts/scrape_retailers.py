"""Script to run web scrapers and collect golf club data."""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.retailer_scrapers.globalgolf_scraper import GlobalGolfScraper
from database.db import db, log_scrape
from database.validation import (
    number, release_year, source_url, stock, refresh_current_price,
    specifications, SPEC_RANGES, SPEC_TEXT,
    handedness, skill_level,
)
from psycopg2.extras import Json


def get_or_create_brand_id(brand_name: str, cursor=None) -> Optional[int]:
    """Get brand ID or create if doesn't exist."""
    if cursor is None:
        with db.get_cursor() as own_cursor:
            return get_or_create_brand_id(brand_name, own_cursor)
    else:
        # Try to find existing brand
        cursor.execute("SELECT id FROM brands WHERE LOWER(name) = LOWER(%s)", (brand_name,))
        result = cursor.fetchone()
        
        if result:
            return result['id']
        
        # Create new brand
        cursor.execute(
            "INSERT INTO brands (name) VALUES (%s) RETURNING id",
            (brand_name,)
        )
        return cursor.fetchone()['id']


def get_club_type_id(club_type: str, cursor=None) -> Optional[int]:
    """Get club type ID."""
    # Normalize club type name
    type_mapping = {
        'drivers': 'Driver',
        'fairway-woods': 'Fairway Wood',
        'hybrids': 'Hybrid',
        'irons': 'Iron',
        'wedges': 'Wedge',
        'putters': 'Putter'
    }
    
    normalized_type = type_mapping.get(club_type.lower(), club_type.title())
    
    if cursor is None:
        with db.get_cursor() as own_cursor:
            return get_club_type_id(club_type, own_cursor)
    else:
        cursor.execute("SELECT id FROM club_types WHERE name = %s", (normalized_type,))
        result = cursor.fetchone()
        return result['id'] if result else None


def import_clubs(clubs: List[dict], source_name: str) -> tuple[int, int]:
    """
    Import scraped clubs into database.
    
    Returns:
        Tuple of (added_count, updated_count)
    """
    added = 0
    updated = 0
    
    with db.get_cursor() as cursor:
        for club_data in clubs:
            try:
                year = release_year(club_data.get('year', club_data.get('year_released')))
                if year is None:
                    continue
                brand = club_data['brand'].strip()
                model = club_data['model'].strip()
                club_type = club_data['club_type'].strip()
                if not brand or not model:
                    raise ValueError("Brand and model are required")
                url = source_url(club_data.get('url'))
                price = number(club_data.get('price'))
                availability = stock(club_data.get('in_stock'))
                variants = specifications(club_data.get('specs', {}))
                hand = handedness(club_data.get('hand'))
                skill = skill_level(club_data.get('skill_level'))
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                print(f"Skipping invalid club: {exc}")
                continue
            brand_id = get_or_create_brand_id(brand, cursor)
            club_type_id = get_club_type_id(club_type, cursor)
            if not club_type_id:
                continue
            cursor.execute(
                """SELECT id FROM golf_clubs
                   WHERE brand_id = %s AND model_name = %s AND year_released = %s""",
                (brand_id, model, year),
            )
            existing = cursor.fetchone()
            if existing:
                club_id = existing['id']
                cursor.execute(
                    """UPDATE golf_clubs SET hand = COALESCE(%s, hand),
                       skill_level = COALESCE(%s, skill_level) WHERE id = %s""",
                    (hand, skill, club_id),
                )
                updated += 1
            else:
                cursor.execute(
                    """INSERT INTO golf_clubs
                       (brand_id, club_type_id, model_name, year_released, source_name, source_url,
                        hand, skill_level)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (brand_id, club_type_id, model, year, source_name, url, hand, skill),
                )
                club_id = cursor.fetchone()['id']
                added += 1
            cursor.execute(
                """
                INSERT INTO product_sources
                    (golf_club_id, source_name, product_url, price, in_stock, price_checked_at)
                VALUES (%s, %s, %s, %s, %s,
                        CASE WHEN %s::numeric IS NOT NULL THEN CURRENT_TIMESTAMP ELSE NULL END)
                ON CONFLICT (golf_club_id, source_name) DO UPDATE
                SET product_url = EXCLUDED.product_url, price = EXCLUDED.price,
                    in_stock = EXCLUDED.in_stock, last_checked = CURRENT_TIMESTAMP,
                    price_checked_at = EXCLUDED.price_checked_at
                """, (club_id, source_name, url, price, availability, price),
            )
            if variants:
                # Replace only this source's observations, preserving other provenance.
                cursor.execute(
                    "DELETE FROM club_specifications WHERE golf_club_id = %s AND source_name = %s",
                    (club_id, source_name),
                )
                fields = list(SPEC_RANGES) + list(SPEC_TEXT)
                columns = ['golf_club_id'] + fields + ['source_name', 'source_url', 'validated', 'raw_specs']
                for variant in variants:
                    cursor.execute(
                        f"INSERT INTO club_specifications ({', '.join(columns)}) "
                        f"VALUES ({', '.join(['%s'] * len(columns))})",
                        [club_id] + [variant.get(field) for field in fields]
                        + [source_name, url, True, Json(club_data['specs'])],
                    )
                cursor.execute("UPDATE golf_clubs SET specs_validated = TRUE WHERE id = %s", (club_id,))
            refresh_current_price(cursor, club_id)
    
    return added, updated


def scrape_globalgolf(club_type: Optional[str] = None, brand: Optional[str] = None):
    """Scrape Global Golf retailer."""
    scraper = GlobalGolfScraper()
    
    try:
        print(f"Scraping Global Golf...")
        clubs = scraper.scrape_clubs(club_type=club_type, brand=brand)
        
        if clubs:
            print(f"Found {len(clubs)} clubs")
            added, updated = import_clubs(clubs, "Global Golf")
            print(f"Added: {added}, Updated: {updated}")
            
            log_scrape(
                source_name="Global Golf",
                scrape_type="full" if not club_type else f"filtered_{club_type}",
                status="success",
                records_added=added,
                records_updated=updated
            )
        else:
            print("No clubs found")
            log_scrape(
                source_name="Global Golf",
                scrape_type="full",
                status="success",
                records_added=0,
                records_updated=0
            )
    
    except Exception as e:
        print(f"Error scraping Global Golf: {str(e)}")
        log_scrape(
            source_name="Global Golf",
            scrape_type="full",
            status="failed",
            error_message=str(e)
        )
    
    finally:
        scraper.close()


def main():
    """Main scraping script."""
    parser = argparse.ArgumentParser(description='Scrape golf club data from retailers')
    parser.add_argument('--source', choices=['globalgolf', 'all'], default='all',
                       help='Which retailer to scrape')
    parser.add_argument('--club-type', help='Filter by club type')
    parser.add_argument('--brand', help='Filter by brand')
    
    args = parser.parse_args()
    
    print("Starting golf club data collection...")
    
    if args.source == 'all' or args.source == 'globalgolf':
        scrape_globalgolf(club_type=args.club_type, brand=args.brand)
    
    # Add more retailers here
    # if args.source == 'all' or args.source == 'pgatoursuperstore':
    #     scrape_pgatoursuperstore()
    
    print("\n✓ Scraping complete!")


if __name__ == "__main__":
    main()
