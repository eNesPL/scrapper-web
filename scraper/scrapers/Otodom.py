import re
import traceback
import os
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import requests
# import datetime # If you need to use datetime objects

FLARE_SOLVERR_URL = "https://flaresolverr.e-nes.eu/v1"

class OtodomScraper(BaseScraper):
    """
    Scraper for Otodom.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Otodom.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania
        # self.base_url = "https://www.otodom.pl" # Example base URL

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Otodom.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        try:
            url = (
                'https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/slaskie/gliwice/gliwice/gliwice?limit=72&ownerTypeSingleSelect=ALL&priceMax=300000&areaMin=35&buildYearMin=1950&roomsNumber=%5BTWO%2CTHREE%5D&floors=%5BGROUND%2CFIRST%5D&by=DEFAULT&direction=DESC&viewType=listing'
            )
            
            # Use FlareSolverr to bypass anti-bot protection
            response = requests.post(
                FLARE_SOLVERR_URL,
                json={
                    "cmd": "request.get",
                    "url": url,
                    "session": "otodom_session",
                    "maxTimeout": 180000
                }
            )
            response.raise_for_status()
            
            return response.json()['solution']['response']
        except Exception as e:
            print(f"[{self.site_name}] Failed to fetch page {page}: {str(e)}")
            return None


    def parse_listings(self, html_content, page=1):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: Tuple of (listings, has_next_page) where:
                 - listings: List of dictionaries, each with at least a 'url'
                 - has_next_page: bool, whether there are more pages to scrape
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Find all listing cards
        for article in soup.find_all('article', {'data-cy': 'listing-item'}):
            link = article.find('a', {'data-cy': 'listing-item-link'})
            if link and link.get('href'):
                listings.append({
                    'url': 'https://www.otodom.pl' + link['href'],
                    'title': link.get_text(strip=True) if link else 'No title'
                })
        
        # Check for next page
        next_page = soup.find('a', {'data-testid': 'pagination-step-next'})
        has_next_page = next_page is not None and page < self.MAX_PAGES
        
        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Otodom.pl with retries.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use FlareSolverr to bypass anti-bot protection
                response = requests.post(
                    FLARE_SOLVERR_URL,
                    json={
                        "cmd": "request.get",
                        "url": listing_url,
                        "session": "otodom_session",
                        "maxTimeout": 120000,
                        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                        "proxy": {
                            "url": os.getenv('PROXY_URL')  # Optional proxy if needed
                        }
                    }
                )
                response.raise_for_status()
                content = response.json()['solution']['response']
                
                # Basic validation of received content
                if "security check" in content.lower() or "captcha" in content.lower():
                    raise ValueError("Anti-bot check detected in response")
                    
                return content
            except Exception as e:
                print(f"[{self.site_name}] Attempt {attempt+1}/{max_retries} failed: {str(e)}")
                if attempt == max_retries - 1:
                    print(f"[{self.site_name}] All attempts failed for {listing_url}")
                    return None


    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        Returns None if essential fields are missing.
        """
        if not html_content:
            return None
            
        soup = BeautifulSoup(html_content, 'html.parser')
        details = {}
        
        # Extract price with validation
        price_elem = soup.find('strong', {'data-cy': 'adPageHeaderPrice'})
        price = price_elem.get_text(strip=True) if price_elem else None
        if price and any(c.isdigit() for c in price):
            details['price'] = price
        else:
            return None  # Reject listings with invalid prices
            
        # Extract area with validation
        area_elem = soup.find('div', {'data-testid': 'table-value-area'})
        if area_elem and 'm²' in area_elem.get_text():
            details['area'] = area_elem.get_text(strip=True)
        else:
            details['area'] = 'N/A'
            
        # Extract description with validation
        description_elem = soup.find('div', {'data-cy': 'adPageAdDescription'})
        if description_elem and len(description_elem.get_text(strip=True)) > 10:
            details['description'] = description_elem.get_text(strip=True)
        else:
            details['description'] = 'No description'
        
        # Count images - more reliable count from gallery container
        gallery = soup.find('div', {'data-cy': 'mosaic-gallery-main-view'})
        images = gallery.find_all('img') if gallery else []
        details['image_count'] = len(images)
        
        # Extract title with fallback
        title_elem = soup.find('h1', {'data-cy': 'adPageAdTitle'})
        details['title'] = title_elem.get_text(strip=True) if title_elem else 'Untitled Listing'
        
        return details
