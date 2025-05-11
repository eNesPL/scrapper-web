import requests
from bs4 import BeautifulSoup
import re

from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class MorizonScraper(BaseScraper):
    """
    Scraper for Morizon.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Morizon.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.base_url = "https://www.morizon.pl"

    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page from Morizon.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :return: HTML content (str) or None.
        """
        # Using the provided example URL
        example_url = "https://www.morizon.pl/mieszkania/do-300000/gliwice/?ps%5Bliving_area_from%5D=25&ps%5Blocation%5D%5Bmap%5D=1&ps%5Blocation%5D%5Bmap_bounds%5D=50.3752324,18.7546442:50.2272469,18.5445885&ps%5Bnumber_of_rooms_from%5D=2&ps%5Bnumber_of_rooms_to%5D=3"
        
        print(f"[{self.site_name}] Fetching listings page using URL: {example_url} (Criteria: {search_criteria})")
        
        try:
            headers = { # Morizon might require some headers to mimic a browser
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
            }
            response = requests.get(example_url, headers=headers, timeout=15)
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
        
        # Common selectors for listing items on Morizon
        # User confirmed that listings are <article class="mz-card">
        
        listing_elements = soup.find_all('article', class_='mz-card')
        
        if not listing_elements:
            print(f"[{self.site_name}] No elements with selector 'article.mz-card' found.")
            # Optional: Add a broader fallback if needed, but for now, stick to user's confirmation.
            # For example, a very generic fallback:
            # listing_elements = soup.find_all('article', href=re.compile(r'^/oferta/'))
            # print(f"[{self.site_name}] Attempting fallback: found {len(listing_elements)} articles with /oferta/ links.")
        else:
            print(f"[{self.site_name}] Found {len(listing_elements)} elements with selector 'article.mz-card'.")


        print(f"[{self.site_name}] Total unique potential listing elements found: {len(listing_elements)}.")

        for item_element in listing_elements:
            summary = {}
            
            # URL and Title
            link_tag = item_element.find('a', href=re.compile(r'^/oferta/'))
            if not link_tag: # Try finding title link specifically
                link_tag = item_element.find(['h2','h3'], class_=['mz-card__title', 'single-result__title--main', 'property-title'])
                if link_tag:
                    link_tag = link_tag.find('a', href=True)
            
            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                summary['url'] = f"{self.base_url}{url if url.startswith('/') else '/' + url}"
                
                # Title: text of the link or a specific title element
                title_text = link_tag.get_text(strip=True)
                if not title_text: # If link itself has no text (e.g. wraps an image)
                    title_h_tag = item_element.find(['h2','h3'], class_=['mz-card__title', 'single-result__title--main', 'property-title'])
                    if title_h_tag:
                        title_text = title_h_tag.get_text(strip=True)
                summary['title'] = title_text if title_text else 'N/A'
            else:
                print(f"[{self.site_name}] Skipping item, no valid URL found.")
                continue

            # Price
            price_tag = item_element.find(['p', 'div'], class_=['mz-card__price', 'single-result__price', 'item-price', 'property-price'])
            if price_tag:
                summary['price'] = price_tag.get_text(strip=True)
            else:
                summary['price'] = 'N/A'

            # Area
            area_tag = item_element.find(['li', 'p', 'div'], class_=['mz-card__params-item--area', 'info-area', 'property-area', 'single-result__info--area'])
            if area_tag:
                summary['area_m2'] = area_tag.get_text(strip=True)
            else: # Fallback: find a param item that contains "m²"
                param_items = item_element.find_all(['li', 'p', 'div'], class_=['mz-card__params-item', 'info-parameter'])
                for param in param_items:
                    if "m²" in param.get_text() and "zł/m²" not in param.get_text():
                        summary['area_m2'] = param.get_text(strip=True)
                        break
                if 'area_m2' not in summary:
                    summary['area_m2'] = 'N/A'
            
            # First Image URL
            img_tag = item_element.find('img', class_=['mz-card__image-thumbnail', 'single-result__image', 'property_image_style'])
            if img_tag:
                img_src = img_tag.get('data-src') or img_tag.get('src')
                if img_src:
                    if img_src.startswith('//'):
                        summary['first_image_url'] = f"https:{img_src}"
                    elif not img_src.startswith('http'):
                        summary['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                    else:
                        summary['first_image_url'] = img_src
                else:
                    summary['first_image_url'] = None
            else:
                summary['first_image_url'] = None

            if summary.get('url'):
                listings.append(summary)
                print(f"[{self.site_name}] Parsed summary: Title: {summary.get('title', 'N/A')[:30]}..., Price: {summary.get('price', 'N/A')}, Area: {summary.get('area_m2', 'N/A')}, URL: {summary.get('url')}")
            else: # Should have been caught by the URL check earlier
                print(f"[{self.site_name}] Item skipped due to missing URL after parsing attempts.")
        
        if not listings and listing_elements:
            print(f"[{self.site_name}] Found {len(listing_elements)} listing elements, but failed to parse details from them. Check selectors and page structure.")
        elif not listing_elements:
            print(f"[{self.site_name}] No listing elements found on the page. Check page structure or selectors.")

        return listings

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Morizon.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        # TODO: Implement actual web request to the listing_url
        pass

    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        :param html_content: str, HTML content of the listing detail page.
        :return: Dictionary with detailed property info.
        """
        print(f"[{self.site_name}] Parsing listing details page content.")
        if not html_content:
            return {}
        # TODO: Implement HTML parsing logic for Morizon.pl listing detail page
        # details = {}
        # details.setdefault('title', 'N/A')
        # details.setdefault('price', 'N/A')
        # details.setdefault('description', 'N/A')
        # details.setdefault('image_count', 0)
        # return details
        return {}
