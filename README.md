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
# Python 3.10+
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
python scripts/init_database.py

# Scrape current inventory
python scripts/scrape_retailers.py --source all

# Load historical data
python scripts/load_historical_data.py --years 10
```

### Scheduled Updates
```bash
# Update prices and availability (run daily)
python scripts/update_prices.py

```

Schedule these commands through your deployment environment. Automated discovery
of new releases is not implemented.

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

### Explainable fitting recommendations

Start `python web/app.py` and open `http://127.0.0.1:5000/recommend`.
The public questionnaire returns up to five options with signed score contributions,
uncertainty, and data limitations. Existing catalogue/admin pages remain authenticated.

Recommendations enforce club type, handedness, budget, explicitly known stock, and
prices checked within 24 hours. Unknown or stale offers are excluded rather than
guessed; the bundled historical sample alone will not produce eligible offers.
Scraper selectors still require verification against permitted real sources.

The default is an explicit heuristic baseline, not a trained ML model. Optional
consented, pseudonymous measured fitting feedback supplies training labels; reviews
are not fitting outcomes. The experimental target is `carry_yards / 400 -
dispersion_yards / 150`, rewarding carry and penalizing lateral dispersion under
comparable conditions. It is not a universal definition of “best,” especially for
putters or target-distance irons/wedges. Prefer a professional fitting for actual
equipment decisions; do not interpret contributions as causal performance gains.

For an existing database, apply the idempotent migration before using these features:

```bash
python scripts/migrate_recommendations.py
```

For a fresh database, use `database/schema.sql` as in Setup. Train from genuinely
collected measurements (no synthetic or review-derived labels):

```bash
python scripts/train_recommender.py --output artifacts/recommender.json
```

Set `RECOMMENDER_MODEL_PATH` to that local JSON artifact. Training uses a time-ordered,
golfer-disjoint holdout, comparison with the baseline, and cold-start reporting.
Insufficient evidence or a failed quality gate leaves baseline serving in place.
JSON artifacts contain evaluation metadata and an outcome-ID consent manifest;
never load model paths supplied by a client. No pre-trained validated model is shipped.

Feedback withdrawal deletes this browser session's records and invalidates affected
model serving. Operators must remove affected exported artifacts/backups and retrain.
See `docs/WEB_INTERFACE.md` for API, privacy, testing, and deployment details.

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
│   ├── migrate_recommendations.py # Upgrade existing databases
│   ├── scrape_retailers.py # Run web scrapers
│   └── update_prices.py   # Update pricing data
├── config/
│   └── brands.json        # Brand configuration
├── data/
│   └── historical/        # Historical club data
├── models/
│   └── club.py           # Catalogue dataclasses, not trained models
├── recommender/          # Additive baseline, Ridge scoring, and evaluation
├── web/                  # Catalogue administration and public fitting flow
├── tests/                # Standard-library unittest regression suite
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
- [x] Ingestion validation and source/price tracking
- [x] Constraint-aware baseline and evaluated ML training pipeline
- [x] Signed local score explanations and fitting feedback API
- [x] Golfer questionnaire and comparison interface
- [ ] Verify production scraper selectors and expand measured fitting data
- [ ] Validate recommendation quality with representative real-world outcomes