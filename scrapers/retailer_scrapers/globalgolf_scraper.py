"""Example scraper for Global Golf website."""

from typing import List, Dict, Any, Optional
from scrapers.base_scraper import BaseScraper


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
            product_url = f"{self.BASE_URL}{link_elem['href']}" if link_elem else None
            
            return {
                'source': self.source_name,
                'brand': brand,
                'model': model,
                'club_type': category,
                'price': price,
                'url': product_url,
                'in_stock': True  # Assume in stock if listed
            }
        
        except Exception as e:
            self.logger.error(f"Error extracting club data: {str(e)}")
            return None
    
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
                'url': club_url,
                'specifications': {}
            }
            
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
                details['rating'] = float(rating_elem.get_text())
            
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
