import requests
from bs4 import BeautifulSoup
import re
try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

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
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Morizon.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        # Using the provided example URL
        example_url = f"https://www.morizon.pl/mieszkania/do-300000/gliwice/?page={page}&ps%5Bliving_area_from%5D=25&ps%5Blocation%5D%5Bmap%5D=1&ps%5Blocation%5D%5Bmap_bounds%5D=50.3752324,18.7546442:50.2272469,18.5445885&ps%5Bnumber_of_rooms_from%5D=2&ps%5Bnumber_of_rooms_to%5D=3"
        
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
        
        listing_elements = soup.find_all('div', class_='card')
        
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
                link_tag = item_element.find(['h2','h3'], class_=['8card__title', 'single-result__title--main', 'property-title'])
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
        try:
            headers = { # Consistent headers
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
            }
            response = requests.get(listing_url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[{self.site_name}] Error fetching details page {listing_url}: {e}")
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
        details = {
            'title': 'N/A',
            'price': 'N/A',
            'area_m2': 'N/A',
            'description': 'N/A',
            'image_count': 0,
            'first_image_url': None
        }

        # Title
        if lxml_html and html_content:
            try:
                tree = lxml_html.fromstring(html_content)
                title_elements = tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/h1')
                if title_elements:
                    details['title'] = title_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Title (XPath): {details['title']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting title with XPath: {e}. Falling back to BeautifulSoup.")

        if details['title'] == 'N/A': # Fallback to BeautifulSoup if XPath failed or lxml not available
            title_tag_bs = soup.find('h1', class_='summary__title')
            if not title_tag_bs: # Fallback if specific class not found
                title_tag_summary_bs = soup.find('div', class_='summary')
                if title_tag_summary_bs:
                    title_tag_bs = title_tag_summary_bs.find('h1')
            if title_tag_bs:
                details['title'] = title_tag_bs.get_text(strip=True)
            print(f"[{self.site_name}] Title (BeautifulSoup fallback): {details['title']}")
        else: # If title was found by XPath
            print(f"[{self.site_name}] Title successfully extracted by XPath: {details['title']}")


        # Price
        if lxml_html and html_content:
            try:
                # Ensure tree is parsed, reuse if already parsed for title
                if 'tree' not in locals() or tree is None:
                    tree = lxml_html.fromstring(html_content)
                
                price_elements = tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/div[1]/div/span[1]')
                if price_elements:
                    details['price'] = price_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Price (XPath): {details['price']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting price with XPath: {e}. Falling back to BeautifulSoup.")

        if details['price'] == 'N/A': # Fallback to BeautifulSoup if XPath failed or lxml not available
            price_tag_bs = soup.find('div', class_='summary__price')
            if price_tag_bs:
                details['price'] = price_tag_bs.get_text(strip=True)
            print(f"[{self.site_name}] Price (BeautifulSoup fallback): {details['price']}")
        else: # If price was found by XPath
            print(f"[{self.site_name}] Price successfully extracted by XPath: {details['price']}")


        description_parts = []

        # Main Description Text
        description_content_div = soup.find('div', class_='description__content')
        if description_content_div:
            # Remove "Pokaż cały opis" button if it's part of the text
            show_more_button = description_content_div.find('button', class_='showMoreDescription')
            if show_more_button:
                show_more_button.decompose()
            
            main_desc_text = description_content_div.get_text(separator='\n', strip=True)
            if main_desc_text:
                description_parts.append(main_desc_text)
                print(f"[{self.site_name}] Main description text found. Length: {len(main_desc_text)}")

        # Area extraction via XPath first
        if lxml_html and html_content:
            try:
                # Ensure tree is parsed, reuse if already parsed for title/price
                if 'tree' not in locals() or tree is None:
                    tree = lxml_html.fromstring(html_content)
                
                # User provided XPath for area
                area_elements = tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/div[2]/span[2]/span')
                if area_elements:
                    details['area_m2'] = area_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Area (XPath): {details['area_m2']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting area with XPath: {e}. Falling back to BeautifulSoup if necessary.")

        # Structured Details from div.FONERK (or similar) to be added to description
        # This replaces the old sections_to_parse logic
        fonerk_divs = soup.find_all('div', class_='FONERK') # Find all such containers
        if not fonerk_divs: # Fallback if FONERK is too specific or dynamic
            # Try to find sections based on h3 followed by divs with the characteristic item structure
            # This is a more complex fallback, for now, we rely on FONERK or similar prominent class
            # if user provides one for such sections.
            # For the provided HTML, FONERK seems to be the key.
            pass

        for fonerk_div in fonerk_divs:
            section_title_tag = fonerk_div.find('h3', class_='gHM061')
            section_title = section_title_tag.get_text(strip=True) if section_title_tag else "Szczegóły"

            # Skip "Ogłoszenie" section from being added to the description
            if section_title.lower() == "ogłoszenie":
                print(f"[{self.site_name}] Skipping section '{section_title}' from description.")
                continue
            
            current_section_details = [f"\n{section_title}:"] # Start with the section title
            
            item_divs = fonerk_div.find_all('div', class_='iT04N1')
            for item_div in item_divs:
                label_span = item_div.find('span', attrs={'data-v-96fcfdf3': True}) # More specific to the example
                value_div = item_div.find('div', attrs={'data-cy': 'itemValue'})
                
                if label_span and value_div:
                    label = label_span.get_text(strip=True)
                    value = value_div.get_text(strip=True)
                    current_section_details.append(f"{label}: {value}")

                    # Fallback for area_m2 if XPath failed and label is "Pow. całkowita" or "Pow. użytkowa"
                    if details['area_m2'] == 'N/A':
                        if "Pow. całkowita" in label or "Pow. użytkowa" in label:
                            details['area_m2'] = value
                            print(f"[{self.site_name}] Area (BeautifulSoup - from FONERK '{label}'): {details['area_m2']}")
            
            if len(current_section_details) > 1: # More than just the title
                description_parts.extend(current_section_details)
                print(f"[{self.site_name}] Added structured details from a FONERK section titled '{section_title}'.")
        
        # Fallback for area_m2 if still not found (e.g. from old propertyDetails__list structure if it exists)
        if details['area_m2'] == 'N/A':
            old_style_sections_to_parse = { "mieszkanie": "Szczegóły mieszkania:"} # Only check 'mieszkanie' for old area
            for h3_text_key, _ in old_style_sections_to_parse.items():
                h3_tag = soup.find('h3', string=lambda t: t and h3_text_key.lower() in t.lower())
                if h3_tag:
                    ul_tag = h3_tag.find_next_sibling('ul', class_='propertyDetails__list')
                    if ul_tag:
                        list_items = ul_tag.find_all('li', class_='propertyDetails__item')
                        for item in list_items:
                            label_tag = item.find('span', class_='propertyDetails__label')
                            value_tag = item.find('span', class_='propertyDetails__value')
                            if label_tag and value_tag:
                                label = label_tag.get_text(strip=True)
                                value = value_tag.get_text(strip=True)
                                if "Pow. użytkowa" in label:
                                    details['area_m2'] = value
                                    print(f"[{self.site_name}] Area (BS fallback - old propertyDetails 'Pow. użytkowa'): {details['area_m2']}")
                                    break
                                elif "Pow. całkowita" in label and details['area_m2'] == 'N/A':
                                    details['area_m2'] = value
                                    print(f"[{self.site_name}] Area (BS fallback - old propertyDetails 'Pow. całkowita'): {details['area_m2']}")
                        if details['area_m2'] != 'N/A': break 

        if description_parts:
            full_description = "\n\n".join(filter(None, description_parts)).strip()
            details['description'] = full_description[:1000] + '...' if len(full_description) > 1000 else full_description
        print(f"[{self.site_name}] Final description length: {len(details['description'])}")


        # Image Count
        photos_counter_button = soup.find(['button', 'a'], class_='summary__photos-counter')
        if photos_counter_button:
            counter_text = photos_counter_button.get_text(strip=True) # e.g., "Zobacz 8 zdjęć"
            match = re.search(r'(\d+)', counter_text)
            if match:
                details['image_count'] = int(match.group(1))
        print(f"[{self.site_name}] Image count: {details['image_count']}")

        # First Image URL
        if lxml_html and html_content:
            try:
                # Ensure tree is parsed, reuse if already parsed for title/price/area
                if 'tree' not in locals() or tree is None:
                    tree = lxml_html.fromstring(html_content)
                
                image_elements_xpath = tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[3]/div[1]/button[1]/img')
                if image_elements_xpath:
                    img_src_xpath = image_elements_xpath[0].get('src')
                    if img_src_xpath:
                        details['first_image_url'] = img_src_xpath
                        print(f"[{self.site_name}] First image URL (XPath): {details['first_image_url']}")
                        # Normalize URL if needed
                        if details['first_image_url'].startswith('//'):
                            details['first_image_url'] = f"https:{details['first_image_url']}"
                        elif not details['first_image_url'].startswith('http'):
                            details['first_image_url'] = f"{self.base_url}{details['first_image_url'] if details['first_image_url'].startswith('/') else '/' + details['first_image_url']}"
            except Exception as e:
                print(f"[{self.site_name}] Error extracting first image URL with XPath: {e}. Falling back to BeautifulSoup.")

        if not details['first_image_url']: # Fallback to BeautifulSoup if XPath failed or lxml not available
            print(f"[{self.site_name}] First image URL not found by XPath, trying BeautifulSoup fallback.")
            # Common Morizon structure for main image:
            # 1. Inside a div with class 'summary__gallery' or 'summary__photos-main'
            # 2. The image itself might be in 'image-gallery__item--main' or directly as an img
            
            # Attempt 1: More specific gallery containers
            main_photo_container_bs = soup.find('div', class_='summary__gallery')
            if not main_photo_container_bs:
                main_photo_container_bs = soup.find('div', class_='summary__photos-main')
            if not main_photo_container_bs: # Another common pattern for the main image wrapper
                main_photo_container_bs = soup.find('div', class_='image-gallery__item--main')
            if not main_photo_container_bs: # A more generic one if others fail
                main_photo_container_bs = soup.find('div', class_='galleryPhotos__photo')

            if main_photo_container_bs:
                img_tag_bs = main_photo_container_bs.find('img')
                if img_tag_bs:
                    img_src_bs = img_tag_bs.get('data-src') or img_tag_bs.get('src')
                    if img_src_bs:
                        if img_src_bs.startswith('//'):
                            details['first_image_url'] = f"https:{img_src_bs}"
                        elif not img_src_bs.startswith('http'):
                            details['first_image_url'] = f"{self.base_url}{img_src_bs if img_src_bs.startswith('/') else '/' + img_src_bs}"
                        else:
                            details['first_image_url'] = img_src_bs
            
            if details['first_image_url']:
                print(f"[{self.site_name}] First image URL (found in specific container via BeautifulSoup): {details['first_image_url']}")
            else:
                # Fallback: Try to find any prominent image if specific containers fail
                print(f"[{self.site_name}] First image not found in specific BS containers, trying broader BS search.")
                content_areas_for_img_bs = soup.find_all(['section', 'article', 'div'], class_=['summary', 'content', 'listingDetails'], limit=3)
                for area_bs in content_areas_for_img_bs:
                    img_tag_fallback_bs = area_bs.find('img')
                    if img_tag_fallback_bs:
                        img_src_fallback_bs = img_tag_fallback_bs.get('data-src') or img_tag_fallback_bs.get('src')
                        if img_src_fallback_bs and not img_src_fallback_bs.startswith('data:image'): # Avoid base64 images
                            if img_src_fallback_bs.startswith('//'):
                                details['first_image_url'] = f"https:{img_src_fallback_bs}"
                            elif not img_src_fallback_bs.startswith('http'):
                                details['first_image_url'] = f"{self.base_url}{img_src_fallback_bs if img_src_fallback_bs.startswith('/') else '/' + img_src_fallback_bs}"
                            else:
                                details['first_image_url'] = img_src_fallback_bs
                            
                            if details['first_image_url']:
                                print(f"[{self.site_name}] First image URL (found in BS fallback area): {details['first_image_url']}")
                                break # Found one
                if not details['first_image_url']:
                     print(f"[{self.site_name}] First image URL still not found after all fallbacks.")

        # Ensure essential fields are not None
        details.setdefault('title', 'N/A')
        details.setdefault('price', 'N/A')
        details.setdefault('description', 'N/A')
        details.setdefault('image_count', 0)
        details.setdefault('area_m2', 'N/A')

        print(f"[{self.site_name}] Parsed details: Price='{details['price']}', Area='{details['area_m2']}', Title='{details['title'][:30]}...'")
        return details
