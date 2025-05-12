import requests
from bs4 import BeautifulSoup
import re

from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class NieruchomosciOnlineScraper(BaseScraper):
    """
    Scraper for Nieruchomosci-Online.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Nieruchomosci-Online.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.base_url = "https://www.nieruchomosci-online.pl"

    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page from Nieruchomosci-Online.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :return: HTML content (str) or None.
        """
        # Using the provided example URL
        example_url = "https://www.nieruchomosci-online.pl/szukaj.html?3,mieszkanie,sprzedaz,,Gliwice:14130,,,,-300000,25,,,,,,2"
        
        print(f"[{self.site_name}] Fetching listings page using URL: {example_url} (Criteria: {search_criteria})")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'DNT': '1', 
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
            response = requests.get(example_url, headers=headers, timeout=20)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page {example_url}: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: List of dictionaries, each with at least a 'url'.
        """
        print(f"[{self.site_name}] Parsing listings page content.")
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Listings are identified by the class 'tile'
        listing_elements = soup.find_all(class_='tile')

        print(f"[{self.site_name}] Found {len(listing_elements)} potential listing elements with class 'tile'.")

        for item_element in listing_elements:
            summary = {}
            
            # URL and Title from <h2 class="name body-lg"><a href="...">...</a></h2>
            title_h2_tag = item_element.find('h2', class_='name') 
            link_tag = title_h2_tag.find('a', href=True) if title_h2_tag else None
            
            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                # Nieruchomosci-Online URLs can be relative
                if url.startswith('//'):
                    summary['url'] = f"https:{url}"
                elif url.startswith('/'):
                    summary['url'] = f"{self.base_url}{url}"
                else: # Assuming it might be a full URL or needs context (like relative to current page path)
                    summary['url'] = url 
                
                summary['title'] = link_tag.get_text(strip=True) if link_tag else 'N/A'
            else:
                print(f"[{self.site_name}] Skipping item, no URL found.")
                continue

            # Price and Area from <p class="title-a primary-display font-bold header-sm">
            # <span>PRICE</span><span class="area">AREA</span>
            price_container_tag = item_element.find('p', class_='title-a') # More specific: 'primary-display'
            if price_container_tag:
                price_span = price_container_tag.find('span', recursive=False) # First span for price
                if price_span:
                    summary['price'] = price_span.get_text(strip=True).replace('\xa0', ' ')
                else:
                    summary['price'] = 'N/A'
                
                area_span = price_container_tag.find('span', class_='area')
                if area_span:
                    summary['area_m2'] = area_span.get_text(strip=True).replace('\xa0', ' ')
                else:
                    summary['area_m2'] = 'N/A'
            else:
                summary['price'] = 'N/A'
                summary['area_m2'] = 'N/A'
            
            # First Image URL from <ul class="thumb-slider __no-click"><li><a><img src="..."></a></li></ul>
            thumb_slider_ul = item_element.find('ul', class_='thumb-slider')
            if thumb_slider_ul:
                img_tag = thumb_slider_ul.find('img') # First img tag within the slider
                if img_tag:
                    img_src = img_tag.get('src') or img_tag.get('data-src') # Prefer src, fallback to data-src
                    if img_src:
                        if img_src.startswith('//'):
                            summary['first_image_url'] = f"https:{img_src}"
                        elif img_src.startswith('/'):
                             summary['first_image_url'] = f"{self.base_url}{img_src}"
                        # Handle cases where base_url might already be part of a relative path if not starting with /
                        elif not img_src.startswith('http') and not img_src.startswith(self.base_url):
                             summary['first_image_url'] = f"{self.base_url}/{img_src.lstrip('/')}"
                        else:
                            summary['first_image_url'] = img_src
                    else:
                        summary['first_image_url'] = None
                else:
                    summary['first_image_url'] = None
            else:
                summary['first_image_url'] = None

            if summary.get('url'):
                listings.append(summary)
                print(f"[{self.site_name}] Parsed summary: Title: {summary.get('title', 'N/A')[:30]}..., Price: {summary.get('price', 'N/A')}, Area: {summary.get('area_m2', 'N/A')}, URL: {summary.get('url')}")

        return listings

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Nieruchomosci-Online.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'DNT': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none', # Assuming direct navigation or first hit
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
            response = requests.get(listing_url, headers=headers, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[{self.site_name}] Error fetching listing details page {listing_url}: {e}")
            return None

    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        :param html_content: str, HTML content of the listing detail page.
        :return: Dictionary with detailed property info.
        """
        print(f"[{self.site_name}] Parsing listing details page content.")
        if not html_content:
            return {}
        # TODO: Implement HTML parsing logic for Nieruchomosci-Online.pl listing detail page
        # from bs4 import BeautifulSoup
        # soup = BeautifulSoup(html_content, 'html.parser')
        # details = {}
        # details['title'] = soup.find('h1', class_='property-title').text.strip() # Example
        # details['price'] = soup.find('div', class_='property-price').text.strip() # Example
        # description_tag = soup.find('div', id='propertyDescription')
        # details['description'] = description_tag.text.strip() if description_tag else 'N/A'
        # image_gallery = soup.find('div', class_='gallery-thumbs')
        # details['image_count'] = len(image_gallery.find_all('img')) if image_gallery else 0
        #
        # details.setdefault('title', 'N/A')
        # details.setdefault('price', 'N/A')
        # details.setdefault('description', 'N/A')
        # details.setdefault('image_count', 0)
        # return details
        return {}
