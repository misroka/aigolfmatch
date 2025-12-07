"""Update prices and availability for golf clubs."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db, log_scrape
from scrapers.retailer_scrapers.globalgolf_scraper import GlobalGolfScraper


def update_prices_from_source(scraper, source_name: str):
    """
    Update prices from a specific retailer.
    
    Args:
        scraper: Scraper instance
        source_name: Name of the retailer
    """
    updated = 0
    errors = 0
    
    try:
        # Get all product sources that need updating (older than 1 day)
        cutoff_time = datetime.now() - timedelta(days=1)
        
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT ps.*, gc.model_name, b.name as brand_name
                FROM product_sources ps
                JOIN golf_clubs gc ON ps.golf_club_id = gc.id
                JOIN brands b ON gc.brand_id = b.id
                WHERE ps.source_name = %s 
                AND ps.last_checked < %s
                ORDER BY ps.last_checked ASC
                LIMIT 100
                """,
                (source_name, cutoff_time)
            )
            sources = cursor.fetchall()
        
        print(f"Found {len(sources)} products to update from {source_name}")
        
        for source in sources:
            try:
                # Scrape updated details
                details = scraper.scrape_club_details(source['product_url'])
                
                if details and 'price' in details:
                    # Update price
                    with db.get_cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE product_sources
                            SET price = %s, 
                                in_stock = %s,
                                last_checked = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (details['price'], details.get('in_stock', True), source['id'])
                        )
                        
                        # Also update main club price
                        cursor.execute(
                            """
                            UPDATE golf_clubs
                            SET current_price = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (details['price'], source['golf_club_id'])
                        )
                    
                    updated += 1
                    print(f"Updated: {source['brand_name']} {source['model_name']} - ${details['price']}")
                
            except Exception as e:
                print(f"Error updating {source['model_name']}: {str(e)}")
                errors += 1
                continue
        
        log_scrape(
            source_name=source_name,
            scrape_type="update_prices",
            status="success" if errors < len(sources) / 2 else "partial",
            records_added=0,
            records_updated=updated,
            error_message=f"{errors} errors" if errors > 0 else None
        )
        
        return updated, errors
    
    except Exception as e:
        print(f"Error updating prices from {source_name}: {str(e)}")
        log_scrape(
            source_name=source_name,
            scrape_type="update_prices",
            status="failed",
            error_message=str(e)
        )
        return 0, 0


def main():
    """Update prices from all retailers."""
    print("Starting price update process...")
    
    total_updated = 0
    total_errors = 0
    
    # Update from Global Golf
    print("\n--- Global Golf ---")
    scraper = GlobalGolfScraper()
    try:
        updated, errors = update_prices_from_source(scraper, "Global Golf")
        total_updated += updated
        total_errors += errors
    finally:
        scraper.close()
    
    # Add more retailers here as they're implemented
    # print("\n--- PGA Tour Superstore ---")
    # scraper = PGATourSuperStoreScraper()
    # try:
    #     updated, errors = update_prices_from_source(scraper, "PGA Tour Superstore")
    #     total_updated += updated
    #     total_errors += errors
    # finally:
    #     scraper.close()
    
    print(f"\n✓ Price update complete!")
    print(f"  Total updated: {total_updated}")
    print(f"  Total errors: {total_errors}")


if __name__ == "__main__":
    main()
