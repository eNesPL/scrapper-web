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
        
        soup = BeautifulSoup(html_content, 'html.parser')
        details = {}

        # Title (combining main title and address/subtitle)
        title_text = 'N/A'
        # Main title, often in <h1>. Specific class from example: 'name' or data-v- attribute
        # Looking for a prominent h1, then trying to refine.
        # Example HTML shows: <h1 data-v-423197c2> Mieszkanie, ul. Bema </h1>
        # And <p class="address" data-v-423197c2> Bema, Sośnica, Gliwice, śląskie </p>
        main_title_tag = soup.find('h1') # General h1 first
        if main_title_tag:
            title_text = main_title_tag.get_text(strip=True)
            # Try to find a more specific address part if available near title
            address_p_tag = main_title_tag.find_next_sibling('p', class_='address') # Common pattern
            if not address_p_tag: # Fallback for other structures
                 # The provided HTML has title and address under a div with class "name"
                 # <div class="name"><h1>...</h1> <p class="address">...</p></div>
                 # Or sometimes section data-id="section-title"
                title_section = soup.find(lambda tag: tag.name == 'div' and tag.find('h1') and tag.find('p', class_='address'))
                if title_section:
                    h1_in_section = title_section.find('h1')
                    p_in_section = title_section.find('p', class_='address')
                    if h1_in_section: title_text = h1_in_section.get_text(strip=True)
                    if p_in_section: title_text += f" - {p_in_section.get_text(strip=True)}"


        details['title'] = title_text

        # Price
        # Example HTML: <div class="price-wrapper"> <strong data-v-0f534888>299&nbsp;000&nbsp;zł</strong> ... </div>
        price_strong_tag = soup.select_one('div.price-wrapper > strong')
        if price_strong_tag:
            details['price'] = price_strong_tag.get_text(strip=True).replace('\xa0', ' ')
        else: # Fallback for other price structures, e.g. section with data-id="section-price"
            price_section = soup.find('section', attrs={'data-id': 'section-price'})
            if price_section:
                price_val_tag = price_section.find(['strong', 'div'], class_=['price', 'value', 'amount']) # Common classes
                if price_val_tag:
                     details['price'] = price_val_tag.get_text(strip=True).replace('\xa0', ' ')
        details.setdefault('price', 'N/A')


        # Description
        # Example HTML: <div data-v-9c715a1c id="description" class="description"> <div data-v-9c715a1c class="text-content"> ... </div></div>
        description_div = soup.find('div', id='description')
        if description_div:
            text_content_div = description_div.find('div', class_='text-content')
            if text_content_div:
                # Collect all p tags and join their text
                paragraphs = text_content_div.find_all('p')
                details['description'] = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            else: # Fallback if no 'text-content' div, take all text from #description
                details['description'] = description_div.get_text(separator="\n", strip=True)
        details.setdefault('description', 'N/A')
        if not details['description'] or details['description'].isspace(): # Check if description is empty or just whitespace
            # Fallback: look for a div with class "description" if id="description" is not fruitful
            desc_class_div = soup.find('div', class_='description')
            if desc_class_div and desc_class_div.find('div', class_='text-content'):
                 paragraphs = desc_class_div.find('div', class_='text-content').find_all('p')
                 details['description'] = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            elif desc_class_div: # Take all text from div.description
                 details['description'] = desc_class_div.get_text(separator="\n", strip=True)


        # Image Count
        # Example HTML: <div class="gallery__counter">1/20</div>
        # Or count images in a gallery container
        image_count = 0
        gallery_counter_tag = soup.find(class_=['gallery__counter', 'gallery-counter']) # Common class names
        if gallery_counter_tag:
            match = re.search(r'/(\d+)', gallery_counter_tag.get_text(strip=True))
            if match:
                image_count = int(match.group(1))
        
        if image_count == 0: # Fallback: try to count image elements in a gallery
            # Common gallery container selectors
            gallery_container = soup.find(['div', 'ul'], class_=['gallery', 'gallery-thumbs', 'swiper-wrapper', 'slick-track'])
            if gallery_container:
                # Count direct img children or li > img or div > img patterns
                images_in_gallery = gallery_container.find_all('img', recursive=True) # Recursive to catch nested images
                # Filter out tiny icons if possible, though hard without more context
                image_count = len(images_in_gallery)

        details['image_count'] = image_count
        
        # Ensure all tracked fields have a default
        details.setdefault('title', 'N/A')
        details.setdefault('price', 'N/A')
        details.setdefault('description', 'N/A')
        details.setdefault('image_count', 0)

        print(f"[{self.site_name}] Parsed details: Title: {details.get('title', 'N/A')[:30]}..., Price: {details.get('price', 'N/A')}, Image Count: {details.get('image_count', 0)}")
        return details
