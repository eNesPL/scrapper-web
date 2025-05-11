import requests
from bs4 import BeautifulSoup
import re # For extracting area
try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

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
        try:
            response = requests.get(listing_url, timeout=10)
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
        if lxml_html and html_content: # Ensure lxml is available and html_content is not None
            try:
                tree = lxml_html.fromstring(html_content)
                title_elements = tree.xpath('/html/body/main/div[2]/div[2]/div/div/div[1]/div[1]/h2')
                if title_elements:
                    details['title'] = title_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Title (XPath): {details['title']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting title with XPath: {e}. Falling back to BeautifulSoup.")
        
        if details['title'] == 'N/A': # Fallback to BeautifulSoup if XPath failed or lxml not available
            title_tag_bs = soup.find('div', class_='title') # Common container for title
            if title_tag_bs:
                h2_title_bs = title_tag_bs.find('h2')
                if h2_title_bs:
                    details['title'] = h2_title_bs.get_text(strip=True)
            if details['title'] == 'N/A': # Further fallback
                h1_tag_bs = soup.find('h1')
                if h1_tag_bs:
                    details['title'] = h1_tag_bs.get_text(strip=True)
                else:
                    h2_fallback_bs = soup.find('h2') # General h2
                    if h2_fallback_bs:
                         details['title'] = h2_fallback_bs.get_text(strip=True)
            print(f"[{self.site_name}] Title (BeautifulSoup fallback): {details['title']}")
        else: # If title was found by XPath
             print(f"[{self.site_name}] Title successfully extracted by XPath: {details['title']}")


        # Price
        if lxml_html and html_content: # Ensure lxml is available and html_content is not None
            try:
                # Assuming tree was already parsed for title or will be parsed if not
                if 'tree' not in locals() or tree is None: # Check if tree exists from title parsing
                    tree = lxml_html.fromstring(html_content)
                
                price_elements = tree.xpath('/html/body/main/div[2]/div[2]/div/div/div[1]/div[2]/div[1]/div[1]')
                if price_elements:
                    details['price'] = price_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Price (XPath): {details['price']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting price with XPath: {e}. Falling back to BeautifulSoup.")

        if details['price'] == 'N/A': # Fallback to BeautifulSoup if XPath failed or lxml not available
            price_div_bs = soup.find('div', class_='price') # Main price display
            if price_div_bs:
                price_strong_bs = price_div_bs.find('strong')
                if price_strong_bs:
                    details['price'] = price_strong_bs.get_text(strip=True)
            if details['price'] == 'N/A': # Fallback from details section
                details_section_price_bs = soup.find('div', class_='oglDetails')
                if details_section_price_bs:
                    price_item_bs = details_section_price_bs.find(lambda tag: tag.name == 'li' and 'Cena:' in tag.get_text())
                    if price_item_bs:
                        price_text_content_bs = price_item_bs.get_text(strip=True)
                        match_bs = re.search(r'Cena:\s*([\d\s]+zł)', price_text_content_bs)
                        if match_bs:
                            details['price'] = match_bs.group(1).strip()
            print(f"[{self.site_name}] Price (BeautifulSoup fallback): {details['price']}")
        else: # If price was found by XPath
            print(f"[{self.site_name}] Price successfully extracted by XPath: {details['price']}")


        # Description and other details from "Szczegóły ogłoszenia" and "Opis oferty"
        description_parts = []
        
        # "Szczegóły ogłoszenia" - including Area extraction via XPath first
        if lxml_html and html_content:
            try:
                if 'tree' not in locals() or tree is None:
                    tree = lxml_html.fromstring(html_content)
                area_elements = tree.xpath('/html/body/main/div[2]/div[2]/div/div/div[1]/div[1]/div[9]/ul/li[2]/span[2]')
                if area_elements:
                    details['area_m2'] = area_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Area (XPath): {details['area_m2']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting area with XPath: {e}. Falling back to BeautifulSoup.")

        details_section = soup.find('div', class_='oglDetails') # Lento uses this class for details block
        if details_section:
            details_list_items = details_section.find_all('li')
            if not details_list_items: # Sometimes it's divs instead of li
                details_list_items = details_section.find_all('div', class_=lambda x: x and x.startswith('param param-'))

            section_details_text = []
            for item in details_list_items:
                item_text = item.get_text(strip=True)
                if item_text:
                    section_details_text.append(item_text)
                    # Fallback for area if XPath failed
                    if details['area_m2'] == 'N/A' and 'Powierzchnia:' in item_text:
                        area_match = re.search(r'Powierzchnia:\s*([\d,.]+\s*m2)', item_text, re.IGNORECASE)
                        if area_match:
                            details['area_m2'] = area_match.group(1).strip()
                            print(f"[{self.site_name}] Area (BeautifulSoup fallback from details list): {details['area_m2']}")
            if section_details_text:
                description_parts.append("Szczegóły ogłoszenia:\n" + "\n".join(section_details_text))
        
        if details['area_m2'] == 'N/A': # Final fallback if not found in oglDetails list items
            print(f"[{self.site_name}] Area not found by XPath or in oglDetails list. Current value: {details['area_m2']}")
        else:
            print(f"[{self.site_name}] Area after all attempts: {details['area_m2']}")


        # "Opis oferty"
        description_header = soup.find('h3', string=re.compile(r'Opis oferty', re.IGNORECASE))
        if description_header:
            description_content_div = description_header.find_next_sibling('div', class_='description')
            if not description_content_div: # Fallback if class is not 'description'
                 description_content_div = description_header.find_next_sibling('div')

            if description_content_div:
                main_description_text = description_content_div.get_text(separator='\n', strip=True)
                if main_description_text:
                    description_parts.append("\nOpis główny:\n" + main_description_text) # Changed label for clarity

        # Add content from specific XPath to description
        if lxml_html and html_content:
            try:
                if 'tree' not in locals() or tree is None:
                    tree = lxml_html.fromstring(html_content)
                
                additional_content_elements = tree.xpath('/html/body/main/div[2]/div[2]/div/div/div[1]/div[1]/div[9]')
                if additional_content_elements:
                    additional_content_text = additional_content_elements[0].text_content().strip()
                    if additional_content_text:
                        description_parts.append("\nDodatkowe informacje (z XPath div[9]):\n" + additional_content_text)
                        print(f"[{self.site_name}] Added content from XPath div[9] to description. Length: {len(additional_content_text)}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting content from XPath div[9]: {e}")

        if description_parts:
            full_description = "\n\n".join(filter(None, description_parts))
            details['description'] = full_description[:1000] + '...' if len(full_description) > 1000 else full_description
        print(f"[{self.site_name}] Description length: {len(details['description'])}")

        # Image count and First Image URL
        # Lento often has a gallery indicator like "1/12"
        gallery_indicator = soup.find('div', class_='counter') # e.g., <div class="counter">1 / 12</div>
        if gallery_indicator:
            indicator_text = gallery_indicator.get_text(strip=True)
            match = re.search(r'\d+\s*/\s*(\d+)', indicator_text)
            if match:
                details['image_count'] = int(match.group(1))
        print(f"[{self.site_name}] Image count from indicator: {details['image_count']}")

        # First image - Lento often uses a main image in a specific div or img tag
        main_image_container = soup.find('div', class_=['photoview', 'main-photo', 'gallery-main-photo'])
        if main_image_container:
            img_tag = main_image_container.find('img')
            if img_tag:
                img_src = img_tag.get('src') or img_tag.get('data-src')
                if img_src:
                    if not img_src.startswith('http'):
                        details['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                    else:
                        details['first_image_url'] = img_src
        
        if not details['first_image_url']: # Fallback if specific container not found
            img_tag_general = soup.find('img', id='photoview_img') # Common ID for main image
            if img_tag_general:
                img_src = img_tag_general.get('src') or img_tag_general.get('data-src')
                if img_src:
                    if not img_src.startswith('http'):
                        details['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                    else:
                        details['first_image_url'] = img_src
        
        # If image count is still 0 but we found a first_image_url, set count to at least 1
        if details['image_count'] == 0 and details['first_image_url']:
            details['image_count'] = 1
            print(f"[{self.site_name}] Image count updated to 1 based on found first_image_url.")

        print(f"[{self.site_name}] First image URL: {details['first_image_url']}")
        
        # Ensure essential fields are not None before returning
        details.setdefault('title', 'N/A')
        details.setdefault('price', 'N/A')
        details.setdefault('description', 'N/A')
        details.setdefault('image_count', 0)
        details.setdefault('area_m2', 'N/A')

        print(f"[{self.site_name}] Parsed details: Price='{details['price']}', Area='{details['area_m2']}', Title='{details['title'][:30]}...'")
        return details
