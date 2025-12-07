# Golf Club Recommender System

A comprehensive system for collecting, maintaining, and analyzing golf club data from major brands (2015-2025).

## Project Overview

This project maintains a complete database of golf clubs from all major brands released in the past 10 years, enabling intelligent club recommendations based on player profiles and preferences.

## Database Schema

The system uses a PostgreSQL database with the following main tables:
- **brands** - Golf equipment manufacturers
- **golf_clubs** - Main club inventory with model details
- **club_specifications** - Technical specs (loft, lie, length, etc.)
- **product_sources** - Pricing and availability from retailers
- **club_reviews** - Aggregated ratings and reviews
- **reviewer_profiles** - Detailed reviewer information for personalized recommendations
- **technologies** - Club technologies and features

See `database/schema.sql` for complete schema.

## Covered Brands

### Priority 1 (Major Brands)
- TaylorMade
- Callaway
- Titleist
- Ping

### Priority 2 (Popular Brands)
- Cobra
- Mizuno
- Srixon
- Cleveland Golf
- Wilson
- PXG

### Priority 3 (Boutique/Specialty)
- Honma
- Tour Edge
- Ben Hogan
- Sub 70
- Nike Golf (discontinued 2016)
- And more...

See `config/brands.json` for the complete list.

## Data Sources

The system collects data from:
- Brand official websites
- Major golf retailers (PGA Tour Superstore, Golf Galaxy, etc.)
- Golf review sites and databases
- Historical product archives

## Setup

### Prerequisites
```bash
# Python 3.9+
python --version

# PostgreSQL 13+
psql --version
```

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd aigolfmatch
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Set up the database
```bash
createdb golf_clubs
psql golf_clubs < database/schema.sql
```

4. Configure environment
```bash
cp .env.example .env
# Edit .env with your database credentials
```

5. Initialize the database
```bash
python scripts/init_database.py
```

## Data Collection

### Initial Data Load
```bash
# Load brand data
python scripts/load_brands.py

# Scrape current inventory
python scripts/scrape_retailers.py --all

# Load historical data
python scripts/load_historical_data.py --years 10
```

### Scheduled Updates
```bash
# Update prices and availability (run daily)
python scripts/update_prices.py

# Check for new releases (run weekly)
python scripts/check_new_releases.py
```

## Usage

### Query the Database
```python
from database.db import get_clubs

# Get all drivers from 2023
clubs = get_clubs(club_type='Driver', year=2023)

# Search by brand
taylormade_clubs = get_clubs(brand='TaylorMade', year_min=2020)

# Get clubs by skill level
beginner_clubs = get_clubs(skill_level='Beginner')
```

### Recommender System (Coming Soon)
```python
from recommender import GolfClubRecommender

recommender = GolfClubRecommender()

# Create user profile
user_profile = {
    'handicap': 14.0,
    'swing_speed_mph': 92,
    'skill_level': 'Intermediate',
    'ball_flight': 'Slight Fade',
    'budget': 1500
}

# Get personalized recommendations
recommendations = recommender.recommend(
    user_profile=user_profile,
    club_type='Iron Set'
)

# Recommendations are based on reviews from similar players
for rec in recommendations:
    print(f"{rec['brand']} {rec['model']} - ${rec['price']}")
    print(f"  Rating from similar players: {rec['similar_player_rating']}/5.0")
```

See `docs/REVIEWER_PROFILES.md` for details on personalized recommendations.

## Project Structure

```
aigolfmatch/
├── database/
│   ├── schema.sql          # Database schema
│   └── db.py              # Database connection utilities
├── scrapers/
│   ├── base_scraper.py    # Base scraper class
│   ├── brand_scrapers/    # Brand-specific scrapers
│   └── retailer_scrapers/ # Retailer scrapers
├── scripts/
│   ├── init_database.py   # Database initialization
│   ├── load_brands.py     # Load brand data
│   ├── scrape_retailers.py # Run web scrapers
│   └── update_prices.py   # Update pricing data
├── config/
│   └── brands.json        # Brand configuration
├── data/
│   └── historical/        # Historical club data
├── models/
│   └── club.py           # Data models
└── requirements.txt       # Python dependencies
```

## Maintenance

The system requires regular maintenance:
- **Daily**: Update prices and availability
- **Weekly**: Check for new releases
- **Monthly**: Validate data quality and completeness
- **Quarterly**: Update historical data and review scraper functionality

## Contributing

When adding new brands or data sources:
1. Update `config/brands.json`
2. Create appropriate scraper in `scrapers/`
3. Test data collection
4. Document any special considerations

## License

MIT License

## Roadmap

- [x] Database schema design
- [x] Brand and data source identification
- [ ] Implement web scrapers
- [ ] Historical data collection
- [ ] Data validation pipeline
- [ ] Recommender algorithm
- [ ] API development
- [ ] Web interface