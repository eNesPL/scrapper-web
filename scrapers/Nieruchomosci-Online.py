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
            headers = { # Nieruchomosci-Online might require some headers
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
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
        
        # Listings are often in <article> tags or <div class="list__item">
        listing_elements = soup.find_all('article', attrs={'data-id-item': True})
        if not listing_elements:
            listing_elements = soup.find_all('div', class_='list__item') # Fallback

        print(f"[{self.site_name}] Found {len(listing_elements)} potential listing elements.")

        for item_element in listing_elements:
            summary = {}
            
            # URL and Title
            link_tag = item_element.find('a', class_='item__link', href=True)
            if not link_tag: # Fallback for title link
                title_h_tag = item_element.find(['h2', 'h3'], class_='item__title')
                if title_h_tag:
                    link_tag = title_h_tag.find_parent('a', href=True) # Link might wrap the title
            
            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                # Nieruchomosci-Online URLs are often relative to the domain or a sub-domain
                if url.startswith('//'):
                    summary['url'] = f"https:{url}"
                elif url.startswith('/'):
                    summary['url'] = f"{self.base_url}{url}"
                else: # Assuming it might be a full URL or needs context
                    summary['url'] = url 
                
                title_tag_in_link = link_tag.find(['h2', 'h3'], class_='item__title')
                if title_tag_in_link:
                    summary['title'] = title_tag_in_link.get_text(strip=True)
                elif link_tag.get_text(strip=True): # Fallback to link's text if no specific title tag
                    summary['title'] = link_tag.get_text(strip=True)
                else:
                    summary['title'] = 'N/A'
            else:
                print(f"[{self.site_name}] Skipping item, no URL found.")
                continue

            # Price
            price_tag = item_element.find('p', class_='price__value')
            if price_tag:
                summary['price'] = price_tag.get_text(strip=True).replace('\xa0', ' ')
            else:
                summary['price'] = 'N/A'

            # Area - often part of the price string or in params list
            area_text = None
            if price_tag and "m²" in price_tag.get_text(): # Check if area is in price string
                price_text_content = price_tag.get_text(strip=True).replace('\xa0', ' ')
                # Example: "265 000 zł35,80 m² 7 402,23 zł/m²"
                match = re.search(r'([\d,\.]+)\s*m²', price_text_content)
                if match:
                    area_text = match.group(1) + " m²"
            
            if not area_text: # Fallback to params list
                params_list = item_element.find('ul', class_='params__list')
                if params_list:
                    for param_item in params_list.find_all('li', class_='params__item'):
                        if "m²" in param_item.get_text() and "zł/m²" not in param_item.get_text():
                            area_text = param_item.get_text(strip=True)
                            break
            summary['area_m2'] = area_text.strip() if area_text else 'N/A'
            
            # First Image URL
            photo_container = item_element.find(['div', 'figure'], class_=['item__photo', 'item__photo_container'])
            if photo_container:
                img_tag = photo_container.find('img')
                if img_tag:
                    img_src = img_tag.get('data-src') or img_tag.get('src')
                    if img_src:
                        if img_src.startswith('//'):
                            summary['first_image_url'] = f"https:{img_src}"
                        elif img_src.startswith('/'):
                             summary['first_image_url'] = f"{self.base_url}{img_src}"
                        elif not img_src.startswith('http'): # Relative path without leading slash
                             summary['first_image_url'] = f"{self.base_url}/{img_src}"
                        else:
                            summary['first_image_url'] = img_src
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
            headers = { # Nieruchomosci-Online might require some headers
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
            }
            response = requests.get(listing_url, headers=headers, timeout=10)
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
