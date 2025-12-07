#!/usr/bin/env python
"""Command-line tool for querying the golf club database."""

import sys
import argparse
from pathlib import Path
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_clubs, get_brands, get_club_types, db


def list_brands():
    """List all brands in the database."""
    brands = get_brands()
    
    table = [[b['name'], b['country'], b['website']] for b in brands]
    headers = ['Brand', 'Country', 'Website']
    
    print(f"\n{len(brands)} brands in database:\n")
    print(tabulate(table, headers=headers, tablefmt='grid'))


def list_club_types():
    """List all club types."""
    types = get_club_types()
    
    table = [[t['name'], t['description']] for t in types]
    headers = ['Club Type', 'Description']
    
    print(f"\n{len(types)} club types:\n")
    print(tabulate(table, headers=headers, tablefmt='grid'))


def search_clubs(brand=None, club_type=None, year=None, skill_level=None, limit=20):
    """Search for clubs with filters."""
    clubs = get_clubs(
        brand=brand,
        club_type=club_type,
        year=year,
        skill_level=skill_level,
        limit=limit
    )
    
    if not clubs:
        print("\nNo clubs found matching criteria.")
        return
    
    table = [
        [
            c['brand_name'],
            c['model_name'],
            c['club_type_name'],
            c['year_released'],
            f"${c['msrp']:.2f}" if c['msrp'] else 'N/A',
            f"${c['current_price']:.2f}" if c['current_price'] else 'N/A',
            c['skill_level'] or 'N/A'
        ]
        for c in clubs
    ]
    
    headers = ['Brand', 'Model', 'Type', 'Year', 'MSRP', 'Current $', 'Skill Level']
    
    print(f"\nFound {len(clubs)} clubs:\n")
    print(tabulate(table, headers=headers, tablefmt='grid'))


def stats():
    """Show database statistics."""
    with db.get_cursor() as cursor:
        # Count brands
        cursor.execute("SELECT COUNT(*) as count FROM brands")
        brand_count = cursor.fetchone()['count']
        
        # Count clubs
        cursor.execute("SELECT COUNT(*) as count FROM golf_clubs")
        club_count = cursor.fetchone()['count']
        
        # Count by club type
        cursor.execute("""
            SELECT ct.name, COUNT(gc.id) as count
            FROM club_types ct
            LEFT JOIN golf_clubs gc ON ct.id = gc.club_type_id
            GROUP BY ct.name
            ORDER BY count DESC
        """)
        type_counts = cursor.fetchall()
        
        # Average prices
        cursor.execute("""
            SELECT 
                AVG(msrp) as avg_msrp,
                AVG(current_price) as avg_current_price,
                MIN(year_released) as min_year,
                MAX(year_released) as max_year
            FROM golf_clubs
            WHERE msrp IS NOT NULL
        """)
        price_stats = cursor.fetchone()
        
        # Top brands
        cursor.execute("""
            SELECT b.name, COUNT(gc.id) as count
            FROM brands b
            LEFT JOIN golf_clubs gc ON b.id = gc.brand_id
            GROUP BY b.name
            HAVING COUNT(gc.id) > 0
            ORDER BY count DESC
            LIMIT 10
        """)
        top_brands = cursor.fetchall()
    
    print("\n=== Database Statistics ===\n")
    print(f"Total Brands: {brand_count}")
    print(f"Total Clubs: {club_count}")
    
    if price_stats['avg_msrp']:
        print(f"Average MSRP: ${price_stats['avg_msrp']:.2f}")
    if price_stats['avg_current_price']:
        print(f"Average Current Price: ${price_stats['avg_current_price']:.2f}")
    
    if price_stats['min_year'] and price_stats['max_year']:
        print(f"Year Range: {price_stats['min_year']} - {price_stats['max_year']}")
    
    print("\n=== Clubs by Type ===\n")
    type_table = [[t['name'], t['count']] for t in type_counts if t['count'] > 0]
    print(tabulate(type_table, headers=['Type', 'Count'], tablefmt='simple'))
    
    if top_brands:
        print("\n=== Top Brands ===\n")
        brand_table = [[b['name'], b['count']] for b in top_brands]
        print(tabulate(brand_table, headers=['Brand', 'Count'], tablefmt='simple'))


def recent_releases(years=2, limit=30):
    """Show recent club releases."""
    from datetime import datetime
    current_year = datetime.now().year
    min_year = current_year - years
    
    clubs = get_clubs(year_min=min_year, limit=limit)
    
    if not clubs:
        print(f"\nNo clubs found from the last {years} years.")
        return
    
    table = [
        [
            c['year_released'],
            c['brand_name'],
            c['model_name'],
            c['club_type_name'],
            f"${c['msrp']:.2f}" if c['msrp'] else 'N/A',
        ]
        for c in clubs
    ]
    
    headers = ['Year', 'Brand', 'Model', 'Type', 'MSRP']
    
    print(f"\nRecent releases (last {years} years):\n")
    print(tabulate(table, headers=headers, tablefmt='grid'))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Query the golf club database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats                              # Show database statistics
  %(prog)s brands                             # List all brands
  %(prog)s types                              # List club types
  %(prog)s search --brand TaylorMade          # Search by brand
  %(prog)s search --type Driver --year 2023   # Search drivers from 2023
  %(prog)s search --skill Beginner            # Find beginner clubs
  %(prog)s recent                             # Show recent releases
  %(prog)s recent --years 5                   # Show releases from last 5 years
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')
    
    # Brands command
    subparsers.add_parser('brands', help='List all brands')
    
    # Types command
    subparsers.add_parser('types', help='List all club types')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for clubs')
    search_parser.add_argument('--brand', help='Filter by brand name')
    search_parser.add_argument('--type', help='Filter by club type')
    search_parser.add_argument('--year', type=int, help='Filter by release year')
    search_parser.add_argument('--skill', help='Filter by skill level')
    search_parser.add_argument('--limit', type=int, default=20, help='Max results (default: 20)')
    
    # Recent command
    recent_parser = subparsers.add_parser('recent', help='Show recent releases')
    recent_parser.add_argument('--years', type=int, default=2, help='Years back (default: 2)')
    recent_parser.add_argument('--limit', type=int, default=30, help='Max results (default: 30)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'stats':
            stats()
        elif args.command == 'brands':
            list_brands()
        elif args.command == 'types':
            list_club_types()
        elif args.command == 'search':
            search_clubs(
                brand=args.brand,
                club_type=args.type,
                year=args.year,
                skill_level=args.skill,
                limit=args.limit
            )
        elif args.command == 'recent':
            recent_releases(years=args.years, limit=args.limit)
    
    except Exception as e:
        print(f"\nError: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
