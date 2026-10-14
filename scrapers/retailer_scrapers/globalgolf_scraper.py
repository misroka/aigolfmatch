"""Example scraper for Global Golf website."""

from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from urllib.parse import urljoin
from scrapers.base_scraper import BaseScraper
from database.validation import release_year


class GlobalGolfScraper(BaseScraper):
    """Scraper for Global Golf retailer."""
    
    BASE_URL = "https://www.globalgolf.com"
    
    def __init__(self):
        super().__init__("Global Golf")
        self.categories = {
            'drivers': '/golf-clubs/drivers/',
            'fairway-woods': '/golf-clubs/fairway-woods/',
            'hybrids': '/golf-clubs/hybrids/',
            'irons': '/golf-clubs/irons/',
            'wedges': '/golf-clubs/wedges/',
            'putters': '/golf-clubs/putters/'
        }
    
    def scrape_clubs(self, club_type: Optional[str] = None, brand: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Scrape golf clubs from Global Golf.
        
        Args:
            club_type: Type of club to scrape (driver, iron, etc.)
            brand: Specific brand to filter
            
        Returns:
            List of club dictionaries
        """
        clubs = []
        
        # Determine which categories to scrape
        if club_type and club_type.lower() in self.categories:
            categories = {club_type.lower(): self.categories[club_type.lower()]}
        else:
            categories = self.categories
        
        for category_name, category_path in categories.items():
            self.logger.info(f"Scraping {category_name} from Global Golf")
            
            url = f"{self.BASE_URL}{category_path}"
            page = 1
            
            while page <= 10:  # Limit to first 10 pages
                params = {'page': page}
                if brand:
                    params['brand'] = brand
                
                soup = self.fetch_page(url, params=params)
                if not soup:
                    break
                
                # Find product listings (this is an example - actual selectors need verification)
                products = soup.find_all('div', class_='product-item')
                
                if not products:
                    break
                
                for product in products:
                    club_data = self._extract_club_data(product, category_name)
                    if club_data:
                        clubs.append(club_data)
                
                page += 1
        
        self.logger.info(f"Scraped {len(clubs)} clubs from Global Golf")
        return clubs
    
    def _extract_club_data(self, product_element, category: str) -> Optional[Dict[str, Any]]:
        """Extract club data from a product element."""
        try:
            # Example extraction (selectors need to be verified with actual site)
            title_elem = product_element.find('h3', class_='product-name')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            
            # Extract brand and model from title
            # This is simplified - actual parsing would be more complex
            parts = title.split(' ', 1)
            brand = parts[0] if parts else None
            model = parts[1] if len(parts) > 1 else title
            
            # Extract price
            price_elem = product_element.find('span', class_='price')
            price = self.extract_price(price_elem.get_text()) if price_elem else None
            
            # Extract product URL
            link_elem = product_element.find('a', class_='product-link')
            product_url = urljoin(self.BASE_URL, link_elem['href']) if link_elem else None
            year_elem = product_element.select_one('[itemprop="releaseDate"], .release-year')
            year = self._release_year(
                product_element.get('data-release-year') or
                (year_elem.get('content') or year_elem.get_text() if year_elem else None))
            
            return {
                'source': self.source_name,
                'brand': brand,
                'model': model,
                'club_type': category,
                'price': price,
                'url': product_url,
                'year': year,
                'in_stock': self._availability(product_element)
            }
        
        except Exception as e:
            self.logger.error(f"Error extracting club data: {str(e)}")
            return None

    @staticmethod
    def _release_year(value):
        try:
            if isinstance(value, str) and len(value) >= 10:
                value = datetime.fromisoformat(value.replace('Z', '+00:00')).year
            return release_year(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _stock_value(value):
        if not isinstance(value, str):
            return None
        value = value.rstrip('/').split('/')[-1].lower()
        if value in ('instock', 'in stock', 'limitedavailability'):
            return True
        if value in ('outofstock', 'out of stock', 'soldout', 'sold out', 'discontinued'):
            return False
        return None

    def _availability(self, element):
        availability = element.select_one('[itemprop="availability"], .availability')
        if availability is None:
            return None
        return self._stock_value(availability.get('href') or availability.get('content')
                                 or self.clean_text(availability.get_text()))

    def _offers(self, soup):
        """Read explicit product offers; fixture-tested, not live-site verified."""
        offers = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or script.get_text())
            except (ValueError, TypeError):
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                nodes.extend(node.get('@graph', []) if isinstance(node.get('@graph'), list) else [])
                types = node.get('@type', [])
                types = [types] if isinstance(types, str) else types
                if 'Product' not in types:
                    continue
                product_offers = node.get('offers', [])
                product_offers = product_offers if isinstance(product_offers, list) else [product_offers]
                offers.extend(offer for offer in product_offers if isinstance(offer, dict))
        # Multiple variants are ambiguous: do not merge a cheap variant's price
        # with a different variant's stock status.
        if not offers:
            return None
        return offers[0] if len(offers) == 1 else {}
    
    def scrape_club_details(self, club_url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape detailed specifications for a specific club.
        
        Args:
            club_url: URL of the club detail page
            
        Returns:
            Dictionary with detailed club information
        """
        soup = self.fetch_page(club_url)
        if not soup:
            return None
        
        try:
            details = {
                'source': self.source_name,
                'url': club_url,
                'specifications': {},
                'price': None,
                'in_stock': None,
            }
            structured_offer = self._offers(soup)
            offer = structured_offer or {}
            currency = offer.get('priceCurrency')
            if currency in (None, 'USD'):
                details['price'] = self.extract_price(offer.get('price'))
            details['in_stock'] = self._stock_value(offer.get('availability'))
            price_elem = soup.select_one('[itemprop="price"], .product-price, span.price')
            if details['price'] is None and structured_offer is None and price_elem:
                currency_elem = soup.select_one('[itemprop="priceCurrency"]')
                currency = currency_elem.get('content') if currency_elem else None
                if currency in (None, 'USD'):
                    details['price'] = self.extract_price(price_elem.get('content') or price_elem.get_text())
            if details['in_stock'] is None and structured_offer is None:
                details['in_stock'] = self._availability(soup)
            year_elem = soup.select_one('[itemprop="releaseDate"], .release-year')
            details['year'] = self._release_year(
                year_elem.get('content') or year_elem.get_text() if year_elem else None)
            
            # Extract title and description
            title_elem = soup.find('h1', class_='product-title')
            if title_elem:
                details['title'] = self.clean_text(title_elem.get_text())
            
            desc_elem = soup.find('div', class_='product-description')
            if desc_elem:
                details['description'] = self.clean_text(desc_elem.get_text())
            
            # Extract specifications table
            spec_table = soup.find('table', class_='specifications')
            if spec_table:
                rows = spec_table.find_all('tr')
                for row in rows:
                    cols = row.find_all(['th', 'td'])
                    if len(cols) >= 2:
                        key = self.clean_text(cols[0].get_text()).lower()
                        value = self.clean_text(cols[1].get_text())
                        details['specifications'][key] = value
            
            # Extract rating
            rating_elem = soup.find('span', class_='rating-value')
            if rating_elem:
                try:
                    details['rating'] = float(rating_elem.get_text())
                except ValueError:
                    pass
            
            # Extract number of reviews
            reviews_elem = soup.find('span', class_='review-count')
            if reviews_elem:
                import re
                count_text = reviews_elem.get_text()
                match = re.search(r'\d+', count_text)
                if match:
                    details['num_reviews'] = int(match.group())
            
            return details
        
        except Exception as e:
            self.logger.error(f"Error scraping club details from {club_url}: {str(e)}")
            return None


if __name__ == "__main__":
    # Test the scraper
    scraper = GlobalGolfScraper()
    
    try:
        # Test scraping drivers
        drivers = scraper.scrape_clubs(club_type='drivers')
        print(f"Found {len(drivers)} drivers")
        
        if drivers:
            print("\nFirst 3 drivers:")
            for driver in drivers[:3]:
                print(driver)
        
    finally:
        scraper.close()
