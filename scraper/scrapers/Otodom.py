import re
import traceback
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
        import requests
        from fake_useragent import UserAgent
        
        print(f"[{self.site_name}] Fetching listings page {page}")
        
        # Updated URL with search[dist] parameter that browsers typically send
        # Updated URL format with proper encoding
        url = (
            'https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/slaskie/gliwice/gliwice/gliwice?limit=72'
            '&ownerTypeSingleSelect=ALL&priceMax=300000&areaMin=35&buildYearMin=1950&roomsNumber=%5BTWO%2CTHREE%5D&by'
            '=DEFAULT&direction=DESC&viewType=listing'
        )
        print(f"[{self.site_name}] Constructed URL: {url}")


    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: Tuple of (listings, has_next_page) where:
                 - listings: List of dictionaries, each with at least a 'url'
                 - has_next_page: bool, whether there are more pages to scrape
        """

        
        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Otodom.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """


    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        :param html_content: str, HTML content of the listing detail page.
        :return: Dictionary with detailed property info.
                 Should include 'price', 'description', 'image_count', 'title'.
        """
        details = {}

        return details
