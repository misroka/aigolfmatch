# Quick Start Guide

Get your golf club database up and running in 15 minutes.

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 13 or higher
- Git

## Step 1: Database Setup (5 min)

```bash
# Create the database
createdb golf_clubs

# Load the schema
psql golf_clubs < database/schema.sql

# Verify tables were created
psql golf_clubs -c "\dt"
```

You should see 10 tables: brands, club_types, golf_clubs, club_specifications, product_sources, club_reviews, technologies, club_technologies, scraping_logs.

## Step 2: Python Environment (3 min)

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Configuration (2 min)

```bash
# Copy environment template
cp .env.example .env

# Edit with your database credentials
nano .env  # or use any text editor
```

Update these values in `.env`:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=golf_clubs
DB_USER=your_username
DB_PASSWORD=your_password
```

## Step 4: Initialize Data (5 min)

```bash
# Load brands, club types, and technologies
python scripts/init_database.py

# Load historical club data (40+ sample clubs)
python scripts/load_historical_data.py --years 10
```

Expected output:
```
Loaded 17 brands
Loaded 8 club types
Loaded 14 technologies
✓ Database initialization complete!

Added: 40+
Skipped: 0
✓ Historical data load complete!
```

## Step 5: Verify Data (1 min)

```bash
# Check what's in the database
psql golf_clubs -c "SELECT COUNT(*) FROM brands;"
psql golf_clubs -c "SELECT COUNT(*) FROM golf_clubs;"
psql golf_clubs -c "SELECT b.name, COUNT(gc.id) FROM brands b LEFT JOIN golf_clubs gc ON b.id = gc.brand_id GROUP BY b.name ORDER BY COUNT(gc.id) DESC LIMIT 10;"
```

## Step 6: Test a Scraper (Optional)

⚠️ **Note**: The scraper selectors are templates and need to be verified/updated to match the actual website structure before running.

```bash
# Test the Global Golf scraper (limited to a few pages)
python scrapers/retailer_scrapers/globalgolf_scraper.py
```

## Query Examples

### Python Interface

```python
from database.db import get_clubs, get_brands

# Get all brands
brands = get_brands()
for brand in brands:
    print(brand['name'])

# Get all drivers from 2023
drivers = get_clubs(club_type='Driver', year=2023)
print(f"Found {len(drivers)} drivers from 2023")

# Get TaylorMade clubs from last 3 years
tm_clubs = get_clubs(brand='TaylorMade', year_min=2022)
for club in tm_clubs:
    print(f"{club['model_name']} ({club['year_released']})")

# Get clubs for beginners
beginner_clubs = get_clubs(skill_level='Beginner', limit=20)
```

### SQL Queries

```sql
-- Top brands by number of clubs
SELECT b.name, COUNT(gc.id) as club_count
FROM brands b
LEFT JOIN golf_clubs gc ON b.id = gc.brand_id
GROUP BY b.name
ORDER BY club_count DESC
LIMIT 10;

-- Average price by club type
SELECT ct.name, 
       COUNT(gc.id) as num_clubs,
       AVG(gc.msrp) as avg_msrp,
       AVG(gc.current_price) as avg_current_price
FROM club_types ct
LEFT JOIN golf_clubs gc ON ct.id = gc.club_type_id
GROUP BY ct.name
ORDER BY avg_msrp DESC;

-- Recent releases (last 2 years)
SELECT b.name as brand, 
       gc.model_name, 
       gc.year_released,
       ct.name as type,
       gc.msrp
FROM golf_clubs gc
JOIN brands b ON gc.brand_id = b.id
JOIN club_types ct ON gc.club_type_id = ct.id
WHERE gc.year_released >= 2023
ORDER BY gc.year_released DESC, b.name;

-- Clubs with specifications
SELECT b.name, 
       gc.model_name,
       cs.loft_degrees,
       cs.shaft_material,
       cs.club_length_inches
FROM golf_clubs gc
JOIN brands b ON gc.brand_id = b.id
LEFT JOIN club_specifications cs ON gc.id = cs.golf_club_id
WHERE cs.id IS NOT NULL
LIMIT 10;
```

## Common Issues

### Issue: "psycopg2 not found"
**Solution**: Install PostgreSQL development headers
```bash
# Ubuntu/Debian
sudo apt-get install libpq-dev python3-dev

# macOS
brew install postgresql
```

### Issue: "Database does not exist"
**Solution**: Create the database first
```bash
createdb golf_clubs
```

### Issue: "Permission denied for database"
**Solution**: Update `.env` with correct credentials or grant permissions
```sql
-- As PostgreSQL superuser
GRANT ALL PRIVILEGES ON DATABASE golf_clubs TO your_username;
```

### Issue: "Scraper returns no results"
**Solution**: The scrapers are templates and need to be customized
- Website structures change frequently
- CSS selectors need to be updated to match current site
- Check the website's robots.txt
- Consider starting with manual data entry

## Step 7: Web Interface (Optional, 5 min)

Access your database through a secure web interface with login authentication.

```bash
# Generate secure credentials
python scripts/setup_web_password.py
```

This will generate:
- `SECRET_KEY` for Flask sessions
- `ADMIN_PASSWORD_HASH` for login

Copy the output to your `.env` file, then:

```bash
# Start the web server
cd web
python app.py
```

Open browser to: `http://127.0.0.1:5000`

**Features:**
- 🔒 Secure login required
- 📊 Dashboard with statistics
- 🔍 Browse clubs with filters
- 🏷️ Brand directory
- 👤 Reviewer profiles
- 🔎 Search functionality
- 📱 Responsive design

See `docs/WEB_INTERFACE.md` for complete documentation.

## Next Steps

1. **Expand the dataset**
   - Add more historical clubs manually
   - Research specification data
   - Cross-reference multiple sources

2. **Implement more scrapers**
   - Study target website HTML structure
   - Update CSS selectors in scraper code
   - Test on small samples first
   - Respect rate limits and ToS

3. **Build the recommender**
   - Define user profiles (handicap, swing speed, budget, etc.)
   - Create similarity algorithms
   - Develop recommendation logic

4. **Enhance the web interface**
   - Add club entry forms
   - Implement review submission
   - Create comparison tools
   - Build recommendation wizard

## Documentation

- **Full Setup**: See `README.md`
- **Web Interface Guide**: See `docs/WEB_INTERFACE.md` 🆕
- **Data Collection Strategy**: See `docs/DATA_COLLECTION_GUIDE.md`
- **Project Status**: See `docs/PROJECT_STATUS.md`
- **Database Schema**: See `database/schema.sql`

## Getting Help

- Check the documentation in the `docs/` folder
- Review example code in `scripts/` and `scrapers/`
- Inspect the database schema in `database/schema.sql`
- Look at data models in `models/club.py`

## Summary

You now have:
- ✅ PostgreSQL database with comprehensive schema
- ✅ 17 golf brands configured
- ✅ 40+ sample clubs loaded (2019-2024)
- ✅ 8 club types defined
- ✅ 14+ technologies cataloged
- ✅ Scraper framework ready
- ✅ Database query utilities
- ✅ Data loading scripts
- ✅ Secure web interface (optional)

**Ready to collect and analyze golf club data!** 🏌️‍♂️
