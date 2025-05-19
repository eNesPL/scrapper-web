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
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Nieruchomosci-Online.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        # Using the provided example URL
        example_url = f"https://www.nieruchomosci-online.pl/szukaj.html?3,mieszkanie,sprzedaz,,Gliwice:14130,,,,-300000,25,,,,,,2,{page}"
        
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
        :return: Tuple of (listings, has_next_page) where:
                 - listings: List of dictionaries, each with at least a 'url'
                 - has_next_page: bool, True if there are more pages to scrape
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

        # Check for next page button
        soup = BeautifulSoup(html_content, 'html.parser')
        next_page = soup.find('a', class_='pagination__next')
        has_next_page = next_page is not None
        
        return listings, has_next_page

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

        # Price & Area
        # Primary attempt based on observed HTML: <div class="price-wrapper"> <strong>PRICE</strong> <span>AREA</span>...</div>
        # XPath suggests a structure like <p>...<span>PRICE</span><span>AREA</span>...</p> which is different.
        # We will try multiple selectors.
        price_text = 'N/A'
        area_text = 'N/A'

        price_wrapper = soup.find('div', class_='price-wrapper')
        if price_wrapper:
            price_strong_tag = price_wrapper.find('strong')
            if price_strong_tag:
                price_text = price_strong_tag.get_text(strip=True).replace('\xa0', ' ')
            # Area might be a span sibling or inside another tag within price_wrapper
            area_span = price_wrapper.find('span', class_='size') # Example class, adjust if needed
            if area_span and 'm²' in area_span.get_text():
                 area_text = area_span.get_text(strip=True).replace('\xa0', ' ')
            elif price_strong_tag: # Check siblings of price if area span not found directly
                area_sibling = price_strong_tag.find_next_sibling('span')
                if area_sibling and 'm²' in area_sibling.get_text():
                     area_text = area_sibling.get_text(strip=True).replace('\xa0', ' ')

        # Fallback based on XPath hint (p > span) - less reliable without specific classes/IDs
        if price_text == 'N/A':
            # Look for a <p> tag containing both price (zł) and area (m²) spans
            potential_p_tags = soup.find_all('p')
            for p_tag in potential_p_tags:
                spans = p_tag.find_all('span', recursive=False)
                if len(spans) >= 2:
                    # Check if spans contain price and area patterns
                    span1_text = spans[0].get_text(strip=True).replace('\xa0', ' ')
                    span2_text = spans[1].get_text(strip=True).replace('\xa0', ' ')
                    if 'zł' in span1_text and 'm²' in span2_text:
                        price_text = span1_text
                        area_text = span2_text
                        break # Found a match based on p > span structure
                    elif 'zł' in span2_text and 'm²' in span1_text: # Check swapped order
                        price_text = span2_text
                        area_text = span1_text
                        break

        # Fallback for price using section[data-id='section-price']
        if price_text == 'N/A':
            price_section = soup.find('section', attrs={'data-id': 'section-price'})
            if price_section:
                price_val_tag = price_section.find(['strong', 'div'], class_=['price', 'value', 'amount'])
                if price_val_tag:
                    price_text = price_val_tag.get_text(strip=True).replace('\xa0', ' ')

        # Fallback for area by searching common parameter lists/tables if not found near price
        if area_text == 'N/A':
             # Look in definition lists (dl), tables (table), or unordered lists (ul) for area
             param_containers = soup.find_all(['dl', 'table', 'ul'], class_=['parameters', 'details-list', 'specification']) # Add more potential classes
             for container in param_containers:
                 items = container.find_all(['dd', 'td', 'li'])
                 for item in items:
                     item_text = item.get_text(strip=True)
                     if 'm²' in item_text and 'zł/m²' not in item_text: # Ensure it's area, not price per m2
                         # Try to find the corresponding label (dt, th, previous li/span)
                         label_tag = item.find_previous(['dt', 'th']) or item.find_previous_sibling(['dt', 'th', 'span', 'li'])
                         if label_tag and ('powierzchnia' in label_tag.get_text(strip=True).lower() or 'area' in label_tag.get_text(strip=True).lower()):
                            area_text = item_text.replace('\xa0', ' ')
                            break
                 if area_text != 'N/A': break # Found area in parameters

        details['price'] = price_text
        details['area_m2'] = area_text # Assuming area includes 'm²' unit

        # Description
        # XPath suggests specific divs, but using IDs/classes is more robust.
        # Try primary target: div#description > div.text-content
        description_text = 'N/A'
        description_div = soup.find('div', id='description')
        if not description_div: # Fallback: find div with class 'description'
            description_div = soup.find('div', class_='description')
        # Further fallback: find section with data-id='description'
        if not description_div:
             description_div = soup.find('section', attrs={'data-id': 'description'})
        if description_div:
            # Try finding a specific content container within the description div
            text_content_div = description_div.find('div', class_='text-content')
            if not text_content_div: # Another common pattern
                 text_content_div = description_div.find('div', class_='description__body')

            if text_content_div:
                # Collect text from paragraphs or the container itself if no paragraphs
                paragraphs = text_content_div.find_all('p', recursive=False) # Direct children first
                if paragraphs:
                    description_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else: # If no <p>, take the whole text content
                    description_text = text_content_div.get_text(separator="\n", strip=True)
            else:
                # Fallback: take all text directly from the found description_div
                # Exclude potential script/style tags if any are nested
                for tag in description_div(['script', 'style']):
                    tag.decompose()
                description_text = description_div.get_text(separator="\n", strip=True)

        # Clean up description if found
        if description_text and description_text != 'N/A':
             # Remove common boilerplate/agent signatures if possible (example pattern)
             lines = description_text.splitlines()
             filtered_lines = [line for line in lines if "oferta wysłana z programu" not in line.lower() and "asari crm" not in line.lower()]
             # Remove leading/trailing whitespace and filter empty lines
             description_text = "\n".join(line.strip() for line in filtered_lines if line.strip())

        details['description'] = description_text if description_text else 'N/A'

        # Append content from detailsWrapper to description
        details_wrapper_div = soup.find('div', id='detailsWrapper')
        if details_wrapper_div:
            # Decompose map link content to avoid including its text if not desired
            map_link_content = details_wrapper_div.find('p', id='map-link-content-bottom')
            if map_link_content:
                map_link_content.decompose()
                
            details_wrapper_text = details_wrapper_div.get_text(separator="\n", strip=True)
            if details_wrapper_text:
                if details['description'] == 'N/A':
                    details['description'] = "" # Initialize if it was N/A
                
                # Clean up the text from detailsWrapper a bit
                lines = details_wrapper_text.splitlines()
                cleaned_lines = []
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line: # Add only non-empty lines
                        # Avoid redundant headers if already captured or not needed
                        if stripped_line.lower() not in ["szczegóły ogłoszenia", "lokalizacja"]:
                             # Replace multiple spaces/tabs with a single space
                            cleaned_line = re.sub(r'\s{2,}', ' ', stripped_line)
                            cleaned_lines.append(cleaned_line)
                
                formatted_details_wrapper_text = "\n".join(cleaned_lines)

                if details['description']: # If description already has content
                    details['description'] += f"\n\n--- Dodatkowe szczegóły ---\n{formatted_details_wrapper_text}"
                else: # If description was empty or N/A
                    details['description'] = formatted_details_wrapper_text
        
        if not details['description']: # Ensure it's 'N/A' if still empty
            details['description'] = 'N/A'


        # Image Count (Keeping existing logic as it wasn't flagged)
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

        # Extract additional details like floor, rooms, year_built, etc.
        details_container = soup.find('div', class_='table-d__changer') # Based on provided HTML snippet
        if not details_container: # Fallback for similar containers
             details_container = soup.find('div', class_='parameters') # Common alternative class
             # Add more fallbacks if needed based on page structure variations

        if details_container:
            items = details_container.find_all('div', class_='table-d__changer--item')
            if not items: # Fallback if items are direct children or use different tags/classes
                 items = details_container.find_all(['li', 'div'], class_=['parameter', 'details-item']) # Example fallback classes

            param_map = {
                'Piętro:': 'floor',
                'Liczba pokoi:': 'rooms',
                'Rok budowy:': 'year_built',
                'Miejsce parkingowe:': 'parking',
                'Stan mieszkania:': 'condition',
                # Add other potential labels here if needed
            }

            for item in items:
                label_tag = item.find('p', class_='body-md')
                value_container = item.find('div', class_='col-b')

                if label_tag and value_container:
                    label_text = label_tag.get_text(strip=True)
                    if label_text in param_map:
                        key = param_map[label_text]
                        # Handle floor specifically as it has multiple spans (e.g., "4 / 4")
                        if key == 'floor':
                            floor_spans = value_container.find_all('span', class_='fsize-a')
                            value_text = "".join(span.get_text(strip=True) for span in floor_spans)
                        else:
                            value_span = value_container.find('span', class_='fsize-a')
                            value_text = value_span.get_text(strip=True) if value_span else '-'
                        
                        details[key] = value_text if value_text != '-' else 'N/A'

        # Extract details from the main details table (div#detailsTable)
        details_table = soup.find('div', id='detailsTable')
        if details_table:
            list_items = details_table.find_all('li', class_='body-md')
            
            details_map = {
                'Typ oferty': 'offer_type',
                'Rynek': 'market',
                'Forma własności': 'ownership',
                'Charakterystyka mieszkania': 'characteristics', # Contains area, rooms, condition - might refine later
                'Budynek': 'building_type',
                'Rozkład mieszkania': 'layout', # Contains floor, layout type
                'Powierzchnia dodatkowa': 'additional_area',
                'Kuchnia': 'kitchen_type',
                'Media': 'media',
                'Miejsce parkingowe': 'parking_details', # Different from the structured parking field
                'Źródło': 'source',
                # Internal listing ID might be in an 'empty' li after 'Źródło'
            }

            for item in list_items:
                strong_tag = item.find('strong')
                if strong_tag:
                    label = strong_tag.get_text(strip=True).replace(':', '')
                    if label in details_map:
                        key = details_map[label]
                        # Get value - might be in a span, a, or just text after strong
                        value_tag = item.find(['span', 'a'])
                        if value_tag:
                             # Special handling for characteristics, layout, etc. if needed
                             if key == 'characteristics':
                                 # Example: "52,50 m², 2 pokoje, 1 łazienka; stan: do remontu"
                                 # Could parse this further if needed, but for now store raw
                                 details[key] = value_tag.get_text(separator=" ", strip=True).replace('\xa0', ' ')
                                 # Extract condition if not already found
                                 if details.get('condition', 'N/A') == 'N/A' and 'stan:' in value_tag.get_text():
                                     condition_match = re.search(r'stan:\s*(.*)', value_tag.get_text(strip=True), re.IGNORECASE)
                                     if condition_match:
                                         details['condition'] = condition_match.group(1).strip()
                             elif key == 'layout':
                                 # Example: "piętro 4/4, jednostronne, dwustronne"
                                 details[key] = value_tag.get_text(separator=" ", strip=True)
                                 # Extract floor if not already found
                                 if details.get('floor', 'N/A') == 'N/A' and 'piętro' in value_tag.get_text():
                                     floor_match = re.search(r'piętro\s*([\d/]+)', value_tag.get_text(strip=True), re.IGNORECASE)
                                     if floor_match:
                                         details['floor'] = floor_match.group(1).strip()
                             else:
                                details[key] = value_tag.get_text(separator=" ", strip=True).replace('\xa0', ' ')
                        else:
                            # If no span/a, try getting text after strong tag
                            value_text = strong_tag.next_sibling
                            if value_text and isinstance(value_text, str):
                                details[key] = value_text.strip().replace('\xa0', ' ')
                    elif label == '': # Handle the internal listing ID case (label is '&nbsp;')
                         prev_li = item.find_previous_sibling('li')
                         if prev_li and prev_li.find('strong') and prev_li.find('strong').get_text(strip=True).startswith('Źródło'):
                             id_span = item.find('span')
                             if id_span and 'numer ogłoszenia:' in id_span.get_text():
                                 match = re.search(r'numer ogłoszenia:\s*([\w-]+)', id_span.get_text())
                                 if match:
                                     details['listing_id_internal'] = match.group(1).strip()


        # Ensure all tracked fields have a default value
        details.setdefault('title', 'N/A')
        details.setdefault('price', 'N/A')
        details.setdefault('area_m2', 'N/A')
        details.setdefault('description', 'N/A')
        details.setdefault('image_count', 0)
        # Add defaults for the new fields
        details.setdefault('floor', 'N/A')
        details.setdefault('rooms', 'N/A')
        details.setdefault('year_built', 'N/A')
        details.setdefault('parking', 'N/A') # From structured data
        details.setdefault('condition', 'N/A') # From structured data or characteristics
        # Add defaults for fields from detailsTable
        details.setdefault('offer_type', 'N/A')
        details.setdefault('market', 'N/A')
        details.setdefault('ownership', 'N/A')
        details.setdefault('characteristics', 'N/A')
        details.setdefault('building_type', 'N/A')
        details.setdefault('layout', 'N/A')
        details.setdefault('additional_area', 'N/A')
        details.setdefault('kitchen_type', 'N/A')
        details.setdefault('media', 'N/A')
        details.setdefault('parking_details', 'N/A') # From details list
        details.setdefault('source', 'N/A')
        details.setdefault('listing_id_internal', 'N/A')


        print(f"[{self.site_name}] Parsed details: Title: {details.get('title', 'N/A')[:30]}..., Price: {details.get('price', 'N/A')}, Area: {details.get('area_m2', 'N/A')}, Rooms: {details.get('rooms', 'N/A')}, Floor: {details.get('floor', 'N/A')}, Image Count: {details.get('image_count', 0)}")
        # print(f"[{self.site_name}] Full parsed details: {details}") # Uncomment for full details debug
        return details
