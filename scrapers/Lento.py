import requests
from bs4 import BeautifulSoup
import re # For extracting area

from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class LentoScraper(BaseScraper):
    """
    Scraper for Lento.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Lento.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.base_url = "https://www.lento.pl"

    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page from Lento.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :return: HTML content (str) or None.
        """
        # Using the provided example URL
        example_url = "https://gliwice.lento.pl/nieruchomosci/mieszkania/sprzedaz.html?price_from=50000&price_to=300000&atr_1_from=20&atr_2_in%5B0%5D=2&atr_2_in%5B1%5D=3"
        
        print(f"[{self.site_name}] Fetching listings page using URL: {example_url} (Criteria: {search_criteria})")
        
        try:
            response = requests.get(example_url, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page {example_url}: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: List of dictionaries, each with at least a 'url', 'title', 'price'.
        """
        print(f"[{self.site_name}] Parsing listings page content.")
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        item_selectors = [
            "div.listing-item.ogl", 
            "article.item",
            "div.item-observe", # Common class on Lento
            "div.common-item", # Another common class
            "li.item",
            "div.row.cat_row" # Sometimes rows are used
        ]
        
        listing_elements = []
        for selector in item_selectors:
            elements = soup.select(selector)
            if elements:
                listing_elements.extend(elements)
                print(f"[{self.site_name}] Found {len(elements)} elements with selector '{selector}'")
        
        listing_elements = list(dict.fromkeys(listing_elements)) # Remove duplicates

        if not listing_elements:
             print(f"[{self.site_name}] No specific item selectors matched. Trying a general approach for divs with links and prices.")
             all_divs_articles = soup.find_all(['div', 'article'])
             potential_items = []
             for item_candidate in all_divs_articles:
                 # Check for a link that looks like a Lento listing URL (contains ,xxxx.html)
                 link_tag = item_candidate.find('a', href=re.compile(r',\d+\.html$'))
                 # Check for a price tag (text ending with zł)
                 price_tag = item_candidate.find(lambda tag: tag.name in ['div', 'p', 'span', 'strong'] and tag.get_text(strip=True).endswith('zł'))
                 if link_tag and price_tag:
                     potential_items.append(item_candidate)
             listing_elements = potential_items
             if listing_elements:
                 print(f"[{self.site_name}] Found {len(listing_elements)} potential items with general approach.")


        print(f"[{self.site_name}] Total unique potential listing elements found: {len(listing_elements)}.")

        for item_element in listing_elements:
            summary = {}
            
            # URL and Title
            link_tag = item_element.find('a', href=re.compile(r',\d+\.html$'))
            if not link_tag:
                title_heading = item_element.find(['h2', 'h3', 'h4'], class_=['title', 'item-title', 'title-A'])
                if title_heading:
                    link_tag = title_heading.find('a', href=True)
            
            if not link_tag:
                link_tag = item_element.find('a', class_=['link', 'abs'], href=True)

            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                if not url.startswith('http'):
                    summary['url'] = f"{self.base_url}{url if url.startswith('/') else '/' + url}"
                else:
                    summary['url'] = url
                
                summary['title'] = link_tag.get_text(strip=True)
                if not summary['title'] or len(summary['title']) < 5 : # If link text is short/empty (e.g. image link)
                    title_tag_alt = item_element.find(['h2','h3','h4'], class_=['title', 'item-title', 'title-A'])
                    if title_tag_alt:
                        summary['title'] = title_tag_alt.get_text(strip=True)
                    else: # Try to get title from img alt attribute if available
                        img_for_title = item_element.find('img', alt=True)
                        if img_for_title:
                            summary['title'] = img_for_title['alt']
                        else:
                            summary['title'] = 'N/A'
            else:
                continue 

            # Price
            price_tag = item_element.find(class_=['price', 'price-label', 'lead', 'priceColor'])
            if price_tag:
                summary['price'] = price_tag.get_text(strip=True)
            else:
                price_tag_alt = item_element.find(lambda tag: tag.name in ['p', 'div', 'span', 'strong'] and tag.get_text(strip=True).endswith('zł'))
                if price_tag_alt:
                     summary['price'] = price_tag_alt.get_text(strip=True)
                else:
                    summary['price'] = 'N/A'

            # First Image URL
            img_tag = item_element.find('img', class_=['main_img', 'photo', 'img-responsive', 'listing-item-image'])
            if not img_tag: # More generic img tag if specific classes fail
                img_container = item_element.find(class_=['photo-container', 'image', 'thumb'])
                if img_container:
                    img_tag = img_container.find('img')
                else:
                    img_tag = item_element.find('img')


            if img_tag:
                img_src = img_tag.get('data-src') or img_tag.get('src') # Prefer data-src if available
                if img_src:
                    if img_src.startswith('data:image'): 
                        summary['first_image_url'] = None
                    elif not img_src.startswith('http'):
                        summary['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                    else:
                        summary['first_image_url'] = img_src
                else:
                    summary['first_image_url'] = None
            else:
                summary['first_image_url'] = None
            
            # Area
            area_text_found = None
            # Look for "X m2" or "Xm2" in various typical elements
            attribute_elements = item_element.find_all(['p', 'div', 'span', 'li'], class_=['info', 'attributes', 'params', 'details', 'listing-item-attributes-value'])
            if not attribute_elements: # If specific classes not found, search all text within the item
                all_text_nodes_in_item = item_element.find_all(string=True, recursive=True)
                item_full_text = " ".join(all_text_nodes_in_item)
                match = re.search(r'(\d[\d\s,.]*)\s*m2', item_full_text, re.IGNORECASE)
                if match:
                    area_text_found = match.group(0) # e.g., "37 m2"
            else:
                for attr_element in attribute_elements:
                    match = re.search(r'(\d[\d\s,.]*)\s*m2', attr_element.get_text(), re.IGNORECASE)
                    if match:
                        area_text_found = match.group(0)
                        break # Found area, no need to check other attribute elements
            
            summary['area_m2'] = area_text_found.strip() if area_text_found else 'N/A'

            if summary.get('url'):
                listings.append(summary)
                print(f"[{self.site_name}] Parsed summary: Title: {summary.get('title', 'N/A')[:30]}..., Price: {summary.get('price', 'N/A')}, Area: {summary.get('area_m2', 'N/A')}, Img: {'Yes' if summary.get('first_image_url') else 'No'}, URL: {summary.get('url')}")
            else:
                print(f"[{self.site_name}] Item skipped due to missing URL after parsing attempts.")
        
        if not listings and listing_elements:
            print(f"[{self.site_name}] Found {len(listing_elements)} listing elements, but failed to parse details from them. Check selectors and page structure.")
        elif not listing_elements:
            print(f"[{self.site_name}] No listing elements found on the page. Check page structure or selectors.")

        return listings

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Lento.pl.
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
        # TODO: Implement HTML parsing logic for Lento.pl listing detail page
        # details = {}
        # details.setdefault('title', 'N/A')
        # details.setdefault('price', 'N/A')
        # details.setdefault('description', 'N/A')
        # details.setdefault('image_count', 0)
        # return details
        return {}
