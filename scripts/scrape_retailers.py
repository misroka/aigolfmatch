"""Script to run web scrapers and collect golf club data."""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.retailer_scrapers.globalgolf_scraper import GlobalGolfScraper
from database.db import db, log_scrape
from models.club import GolfClub


def get_or_create_brand_id(brand_name: str) -> Optional[int]:
    """Get brand ID or create if doesn't exist."""
    with db.get_cursor() as cursor:
        # Try to find existing brand
        cursor.execute("SELECT id FROM brands WHERE name ILIKE %s", (brand_name,))
        result = cursor.fetchone()
        
        if result:
            return result['id']
        
        # Create new brand
        cursor.execute(
            "INSERT INTO brands (name) VALUES (%s) RETURNING id",
            (brand_name,)
        )
        return cursor.fetchone()['id']


def get_club_type_id(club_type: str) -> Optional[int]:
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
    
    with db.get_cursor() as cursor:
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
    
    for club_data in clubs:
        try:
            # Get or create brand
            brand_id = get_or_create_brand_id(club_data['brand'])
            if not brand_id:
                continue
            
            # Get club type
            club_type_id = get_club_type_id(club_data['club_type'])
            if not club_type_id:
                continue
            
            # Check if club already exists
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM golf_clubs 
                    WHERE brand_id = %s AND model_name = %s
                    """,
                    (brand_id, club_data['model'])
                )
                existing = cursor.fetchone()
            
            if existing:
                # Update price
                club_id = existing['id']
                if club_data.get('price'):
                    with db.get_cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE golf_clubs 
                            SET current_price = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (club_data['price'], club_id)
                        )
                    updated += 1
            else:
                # Insert new club
                with db.get_cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO golf_clubs (
                            brand_id, club_type_id, model_name, 
                            current_price, year_released
                        ) VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            brand_id,
                            club_type_id,
                            club_data['model'],
                            club_data.get('price'),
                            2024  # Default year, should be extracted from data
                        )
                    )
                    club_id = cursor.fetchone()['id']
                    added += 1
            
            # Add product source entry
            if club_data.get('url'):
                with db.get_cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO product_sources (
                            golf_club_id, source_name, product_url, 
                            price, in_stock
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (golf_club_id, source_name) DO UPDATE
                        SET product_url = EXCLUDED.product_url,
                            price = EXCLUDED.price,
                            in_stock = EXCLUDED.in_stock,
                            last_checked = CURRENT_TIMESTAMP
                        """,
                        (
                            club_id,
                            source_name,
                            club_data['url'],
                            club_data.get('price'),
                            club_data.get('in_stock', True)
                        )
                    )
        
        except Exception as e:
            print(f"Error importing club {club_data.get('model')}: {str(e)}")
            continue
    
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
