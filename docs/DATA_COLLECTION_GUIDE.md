# Golf Club Data Collection Guide

## Overview

This system collects and maintains a comprehensive database of golf clubs from all major brands released in the past 10 years (2015-2025).

## Data Collection Strategy

### 1. Data Sources

#### Primary Sources (Brand Websites)
- **Pros**: Official specs, accurate release dates, complete product lines
- **Cons**: May not show discontinued products, vary in structure
- **Brands to scrape**: TaylorMade, Callaway, Titleist, Ping, Mizuno, etc.

#### Secondary Sources (Retailers)
- **Global Golf** - Large inventory including used clubs
- **PGA Tour Superstore** - Current models, good pricing
- **Golf Galaxy** - Wide selection
- **2nd Swing** - New and used, detailed trade-in data
- **Rock Bottom Golf** - Deals and closeouts

#### Tertiary Sources (Review Sites)
- **MyGolfSpy** - Detailed reviews and testing data
- **Golf Digest** - Hot List and reviews
- **GolfWRX** - Forum discussions and reviews

### 2. Data to Collect

#### Essential Data
- Brand name
- Model name
- Year released
- Club type (Driver, Fairway Wood, Hybrid, Iron, Wedge, Putter)
- MSRP / Original price
- Current price
- Availability status

#### Detailed Specifications
- Loft options (degrees)
- Lie angle (degrees)
- Club length (inches)
- Swing weight
- Shaft material (Steel, Graphite, Carbon)
- Shaft flex options (X, S, R, A, L)
- Shaft model/brand
- Grip model
- Club head material
- Club head volume (for drivers)
- Adjustability features
- Weight configuration

#### Marketing/Technical
- Technologies used (e.g., Jailbreak, Twist Face)
- Target skill level (Beginner, Intermediate, Advanced, Professional)
- Target handicap range
- Gender (Men's, Women's, Junior's)
- Hand orientation (Right, Left)
- Product description

#### Market Data
- Customer ratings
- Number of reviews
- Price history
- Retailer availability

### 3. Historical Data Collection

#### Manual Research Required
For clubs from 2015-2020, manual research may be needed:

1. **Brand Archive Pages**
   - Many brands have product archives
   - Check wayback machine (archive.org) for old product pages

2. **Golf Forums**
   - GolfWRX archives have detailed discussions
   - Club reviews often include specs

3. **Golf Publications**
   - Golf Digest Hot List archives (annual)
   - MyGolfSpy Most Wanted testing (annual)

4. **Retail Historical Data**
   - Global Golf has extensive used club database
   - eBay sold listings show historical availability

#### Key Release Years by Brand

**TaylorMade**
- 2025: Qi10 series
- 2024: Qi10 series
- 2023: Stealth 2 series
- 2022: Stealth series
- 2021: SIM2 series
- 2020: SIM series
- 2019: M5/M6 series
- 2018: M3/M4 series
- 2017: M1/M2 series
- 2016: M1/M2 series
- 2015: R15 series

**Callaway**
- 2024: Paradym Ai Smoke
- 2023: Paradym series
- 2022: Rogue ST series
- 2021: Epic Speed/Max
- 2020: Mavrik series
- 2019: Epic Flash
- 2018: Rogue series
- 2017: Epic series
- 2016: XR series
- 2015: XR series

**Titleist**
- 2023: TSR series
- 2021: TSi series
- 2019: TS series
- 2017: 718 series irons, TS drivers
- 2015: 716 series irons

**Ping**
- 2023: G430 series
- 2021: G425 series
- 2019: G410 series
- 2017: G400 series
- 2016: G series

### 4. Scraper Implementation Priority

#### Phase 1 (Immediate)
1. ✅ Database schema
2. ✅ Base scraper framework
3. ✅ Historical data structure
4. Global Golf scraper (template created)
5. Load historical data (2020-2025)

#### Phase 2 (Next Week)
1. PGA Tour Superstore scraper
2. Golf Galaxy scraper
3. Brand website scrapers (TaylorMade, Callaway)
4. Expand historical data (2015-2019)

#### Phase 3 (Month 1)
1. Review site integration
2. Price tracking automation
3. Data quality validation
4. Duplicate detection and merging

#### Phase 4 (Ongoing)
1. Weekly new release monitoring
2. Daily price updates
3. Quarterly data completeness audit
4. Expand to additional brands

### 5. Data Quality Measures

#### Validation Rules
- Brand name must match known brands list
- Year must be between 2015-2025
- Prices must be reasonable ($50-$10,000)
- Model names should be unique per brand/year
- Required fields: brand, model, year, club_type

#### Deduplication
- Match on: brand + model + year
- Fuzzy matching for variations (e.g., "P790" vs "P·790")
- Manual review queue for ambiguous matches

#### Data Completeness Tracking
- Track percentage of clubs with specs
- Monitor data freshness (last updated)
- Flag missing critical data

### 6. Maintenance Schedule

#### Daily Tasks
- Update prices from major retailers
- Check for scraper errors
- Monitor data quality alerts

#### Weekly Tasks
- Check brand websites for new releases
- Run deduplication checks
- Review and approve pending matches

#### Monthly Tasks
- Audit data completeness
- Update historical data for new discoveries
- Performance optimization

#### Quarterly Tasks
- Comprehensive data validation
- Expand brand coverage
- Update scraper selectors (sites change)
- Backup database

### 7. Legal and Ethical Considerations

#### Best Practices
- Respect robots.txt
- Rate limiting (2 seconds between requests)
- Use proper User-Agent headers
- Cache results to minimize requests
- Only collect publicly available data
- Don't scrape behind login walls

#### Terms of Service
- Review each site's ToS before scraping
- Some sites explicitly prohibit scraping
- Consider API options where available
- Be prepared to use manual data entry

### 8. Next Steps

1. **Test the scraper framework**
   ```bash
   # Set up environment
   cp .env.example .env
   # Edit .env with database credentials
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Initialize database
   createdb golf_clubs
   psql golf_clubs < database/schema.sql
   python scripts/init_database.py
   ```

2. **Load historical data**
   ```bash
   python scripts/load_historical_data.py --years 10
   ```

3. **Test scraping** (Note: selectors need verification)
   ```bash
   python scripts/scrape_retailers.py --source globalgolf
   ```

4. **Expand data sources**
   - Implement additional retailer scrapers
   - Add brand website scrapers
   - Integrate review aggregation

5. **Build recommender**
   - Analyze collected data
   - Develop recommendation algorithm
   - Create API endpoints

## Resources

### Useful Links
- [MyGolfSpy Hot List](https://mygolfspy.com/most-wanted/)
- [Golf Digest Equipment](https://www.golfdigest.com/equipment)
- [GolfWRX Forums](https://forums.golfwrx.com/)
- [Global Golf Used Clubs](https://www.globalgolf.com/used-golf-clubs/)

### Tools
- BeautifulSoup4 - HTML parsing
- Selenium - Dynamic content
- Scrapy - Advanced scraping framework
- PostgreSQL - Data storage
- Pandas - Data analysis
