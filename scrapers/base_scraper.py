"""Base scraper class for web scraping golf club data."""

import time
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential
from ratelimit import limits, sleep_and_retry
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class BaseScraper(ABC):
    """Base class for all web scrapers."""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"scraper.{source_name}")
        self.user_agent = UserAgent()
        self.session = requests.Session()
        self.request_delay = float(os.getenv('REQUEST_DELAY', '2'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        
    def get_headers(self) -> Dict[str, str]:
        """Generate request headers with random user agent."""
        return {
            'User-Agent': self.user_agent.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    @sleep_and_retry
    @limits(calls=30, period=60)  # Rate limit: 30 calls per minute
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_page(self, url: str, params: Optional[Dict] = None) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a web page.
        
        Args:
            url: URL to fetch
            params: Optional query parameters
            
        Returns:
            BeautifulSoup object or None if failed
        """
        try:
            self.logger.info(f"Fetching: {url}")
            response = self.session.get(
                url,
                headers=self.get_headers(),
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            return BeautifulSoup(response.content, 'lxml')
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def extract_price(self, price_text: str) -> Optional[float]:
        """
        Extract price from text.
        
        Args:
            price_text: Text containing price
            
        Returns:
            Float price or None
        """
        if not price_text:
            return None
        
        # Remove currency symbols and commas
        import re
        price_text = re.sub(r'[^\d.]', '', price_text)
        
        try:
            return float(price_text)
        except (ValueError, TypeError):
            return None
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    @abstractmethod
    def scrape_clubs(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Scrape golf clubs from the source.
        Must be implemented by subclasses.
        
        Returns:
            List of club dictionaries
        """
        pass
    
    @abstractmethod
    def scrape_club_details(self, club_url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape detailed information for a specific club.
        Must be implemented by subclasses.
        
        Args:
            club_url: URL of the club detail page
            
        Returns:
            Dictionary with club details or None
        """
        pass
    
    def close(self):
        """Clean up resources."""
        self.session.close()
