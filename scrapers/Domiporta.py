# In a real scraper, you would import libraries like requests and BeautifulSoup:
# import requests
# from bs4 import BeautifulSoup
import requests
from bs4 import BeautifulSoup
try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class DomiportaScraper(BaseScraper):
    """
    Scraper for Domiporta.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Domiporta.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.base_url = "https://www.domiporta.pl"
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Domiporta.pl.
        :param search_criteria: dict, search parameters (ignored as we use hardcoded URL).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        self.base_url = "https://www.domiporta.pl"
        url = "https://www.domiporta.pl/mieszkanie/sprzedam/slaskie/gliwice?Surface.From=25&Price.To=300000&Rooms.From=2&Pietro.To=1"
        print(f"[{self.site_name}] Fetching listings page: {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'pl-PL,pl;q=0.9',
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: Tuple of (listings, has_next_page) where:
                 - listings: List of dictionaries, each with at least a 'url'
                 - has_next_page: bool, whether there are more pages to scrape
        """
        print(f"[{self.site_name}] Parsing listings page content.")
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Select items that have both 'grid-item' and 'grid-item--cover' classes,
        # but exclude those that also have 'grid-item--special'.
        listing_items = soup.select('.grid-item.grid-item--cover:not(.grid-item--special)')
        print(f"[{self.site_name}] Found {len(listing_items)} listing sections matching new criteria")

        for item in listing_items:
            # Extract URL
            link_tag = item.find('a', href=lambda href: href and '/nieruchomosci/' in href)
            if not link_tag:
                link_tag = item.find('a', class_='offer-item__link')  # Alternative selector
            url = f"{self.base_url}{link_tag['href']}" if link_tag else 'N/A'

            # Extract title
            title_tag = item.find('h2') or item.find('a', class_='offer-item__link') or item.find('span', class_='offer-item-title')
            title = title_tag.get_text(strip=True) if title_tag else 'N/A'

            # Extract price
            price_tag = item.find(attrs={"itemprop": "price"}) or item.find('div', class_='price') or item.find('span', class_='price')
            price = price_tag.get_text(strip=True).replace('\xa0', ' ') if price_tag else 'N/A'

            # Extract area and rooms
            details = {}
            area_tag = item.find('div', class_='paramIconFloorArea')
            if area_tag:
                details['area_m2'] = area_tag.get_text(strip=True).replace('\xa0', ' ')
                
            rooms_tag = item.find('div', string=lambda t: t and 'Liczba pokoi' in t)
            if rooms_tag:
                details['rooms'] = rooms_tag.find_next_sibling('div').get_text(strip=True)

            # Extract first image URL
            img_tag = item.find('img', class_='thumbnail__img')
            first_image_url = img_tag['src'] if img_tag else None
            if first_image_url and first_image_url.startswith('//'):
                first_image_url = f"https:{first_image_url}"

            listings.append({
                'url': url,
                'title': title,
                'price': price,
                'area_m2': details.get('area_m2', 'N/A'),
                'rooms': details.get('rooms', 'N/A'),
                'first_image_url': first_image_url
            })

        print(f"[{self.site_name}] Parsed {len(listings)} listings")
        # Check for next page button
        next_page = soup.find('a', class_='next')
        has_next_page = next_page is not None and len(listings) > 0
        
        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Domiporta.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'pl-PL,pl;q=0.9',
                'Referer': 'https://www.domiporta.pl/'
            }
            response = requests.get(listing_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Check if we got a valid HTML response
            if 'text/html' not in response.headers.get('Content-Type', ''):
                print(f"[{self.site_name}] Invalid content type for {listing_url}")
                return None
                
            return response.text
        except requests.RequestException as e:
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

        # Title
        title_tag = soup.find('h1')
        details['title'] = title_tag.get_text(strip=True) if title_tag else 'N/A'

        # Price
        price_tag = soup.find(attrs={"itemprop": "price"}) or soup.find('div', class_='price')
        details['price'] = price_tag.get_text(strip=True).replace('\xa0', ' ') if price_tag else 'N/A'

        # Area
        area_text = None

        # Method 0: Try XPath with lxml if available
        if lxml_html and html_content: # Ensure html_content is not None
            try:
                tree = lxml_html.fromstring(html_content)
                # User-provided XPath
                xpath_expression = "/html/body/div[1]/article/div[2]/div/div/div[3]/div/section/div/div[1]/div/div/p[2]"
                elements = tree.xpath(xpath_expression)
                if elements:
                    # lxml's text_content() handles <sup> tags correctly by including their text.
                    extracted_value = elements[0].text_content().strip().replace('\xa0', ' ')
                    if extracted_value and any(char.isdigit() for char in extracted_value):
                        temp_check_val = extracted_value.lower().replace(' ', '').replace(',', '.')
                        if not (temp_check_val == 'm2' or temp_check_val == 'm²'):
                            area_text = extracted_value
                            print(f"[{self.site_name}] Area extracted using XPath: {area_text}")
            except Exception as e:
                print(f"[{self.site_name}] Error using XPath for area: {e}. Falling back to BeautifulSoup methods.")
        elif not lxml_html:
            print(f"[{self.site_name}] lxml library not available. Skipping XPath method for area. Consider installing with 'pip install lxml'.")


        # Method 1: Find the label "POWIERZCHNIA" and then its corresponding value (BeautifulSoup).
        if area_text is None:
            # This is inspired by the structure often found, like:
            # <div>
            #   <p class="features-short__name">POWIERZCHNIA</p>
            #   <p class="features-short__value-quadric">27,19 m<sup>2</sup></p>
            # </div>
            area_label_tag = soup.find('p', class_='features-short__name', string=lambda t: t and 'POWIERZCHNIA' in t.strip())
            if area_label_tag:
                area_value_tag = area_label_tag.find_next_sibling('p')
                if area_value_tag:
                    # Handle potential <sup> tag within the area value
                    for sup_tag in area_value_tag.find_all('sup'):
                        sup_tag.unwrap() # Replaces <sup> tag with its content

                    extracted_value = area_value_tag.get_text(strip=True).replace('\xa0', ' ')
                    if extracted_value and any(char.isdigit() for char in extracted_value):
                        # Further check: avoid accepting just "m2" or "m²"
                        temp_check_val = extracted_value.lower().replace(' ', '').replace(',', '.') # Normalize comma to dot
                        if not (temp_check_val == 'm2' or temp_check_val == 'm²'):
                            area_text = extracted_value
                else:
                    print(f"[{self.site_name}] Method 1: Found area label but no sibling 'p' tag for value.")
            else:
                # Fallback within Method 1: if the label-based approach fails, try finding by 'features-short__value-quadric' directly
                # This might be useful if the "POWIERZCHNIA" label is missing or different, but the value tag is present.
                print(f"[{self.site_name}] Method 1: Area label 'POWIERZCHNIA' not found with class 'features-short__name'. Trying direct find for value.")
                area_quadric_p_tag = soup.find('p', class_='features-short__value-quadric')
                if area_quadric_p_tag:
                    for sup_tag in area_quadric_p_tag.find_all('sup'):
                        sup_tag.unwrap()
                    extracted_value = area_quadric_p_tag.get_text(strip=True).replace('\xa0', ' ')
                    if extracted_value and any(char.isdigit() for char in extracted_value):
                        temp_check_val = extracted_value.lower().replace(' ', '').replace(',', '.')
                        if not (temp_check_val == 'm2' or temp_check_val == 'm²'):
                            area_text = extracted_value

        # Method 2: Try list/span format (e.g., features__item_name / features__item_value)
        # Example: <span class="features__item_name">Powierzchnia</span> <span class="features__item_value">55 m²</span>
        if area_text is None:
            # Look for a span containing "Powierzchnia" (more generic than "Powierzchnia całkowita")
            area_name_span = soup.find('span', class_='features__item_name', string=lambda t: t and 'Powierzchnia' in t.strip())
            if area_name_span:
                area_value_span = area_name_span.find_next_sibling('span', class_='features__item_value')
                if area_value_span:
                    extracted_value = area_value_span.get_text(strip=True).replace('\xa0', ' ')
                    if extracted_value and any(char.isdigit() for char in extracted_value):
                        temp_check_val = extracted_value.lower().replace(' ', '')
                        if not (temp_check_val == 'm2' or temp_check_val == 'm²'):
                            area_text = extracted_value
        
        # Method 3: Try common semantic HTML for key-value pairs (dt/dd, th/td)
        if area_text is None:
            # Search for <dt>Termin</dt> <dd>Definicja</dd> or <th>Nagłówek</th> <td>Dane</td>
            # Find label elements (dt, th) containing "Powierzchnia"
            label_elements = soup.find_all(['dt', 'th'], string=lambda t: t and 'Powierzchnia' in t.strip())
            for label_element in label_elements:
                value_element = None
                if label_element.name == 'dt':
                    value_element = label_element.find_next_sibling('dd')
                elif label_element.name == 'th':
                    value_element = label_element.find_next_sibling('td')
                
                if value_element:
                    extracted_value = value_element.get_text(strip=True).replace('\xa0', ' ')
                    if extracted_value and any(char.isdigit() for char in extracted_value):
                        temp_check_val = extracted_value.lower().replace(' ', '')
                        if not (temp_check_val == 'm2' or temp_check_val == 'm²'):
                            area_text = extracted_value
                            break # Found a plausible value from a key-value pair
        
        # Method 4: Fallback to 'paramIconFloorArea' (more common on listing cards than detail pages)
        if area_text is None:
            area_tag = soup.find('div', class_='paramIconFloorArea')
            if area_tag:
                extracted_value = area_tag.get_text(strip=True).replace('\xa0', ' ')
                if extracted_value and any(char.isdigit() for char in extracted_value):
                    temp_check_val = extracted_value.lower().replace(' ', '')
                    if not (temp_check_val == 'm2' or temp_check_val == 'm²'):
                        area_text = extracted_value
        
        details['area_m2'] = area_text if area_text is not None else 'N/A'

        # Description
        details['description'] = 'N/A' # Default to N/A
        extracted_description_text = None

        # Method 1: itemprop="description"
        description_element_itemprop = soup.find(attrs={"itemprop": "description"})
        if description_element_itemprop:
            paragraphs = description_element_itemprop.find_all('p')
            if paragraphs:
                extracted_description_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            else:
                extracted_description_text = description_element_itemprop.get_text(separator="\n", strip=True)
            
            if extracted_description_text and extracted_description_text.strip():
                print(f"[{self.site_name}] Description found using itemprop. Length: {len(extracted_description_text)}")
            else:
                extracted_description_text = None # Reset if empty
                print(f"[{self.site_name}] Description itemprop element found, but no text content.")
        
        # Method 2: class 'description__text' (often used on Domiporta)
        if not extracted_description_text:
            description_div_text_class = soup.find('div', class_='description__text')
            if description_div_text_class:
                paragraphs = description_div_text_class.find_all('p')
                if paragraphs:
                    extracted_description_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else:
                    extracted_description_text = description_div_text_class.get_text(separator="\n", strip=True)

                if extracted_description_text and extracted_description_text.strip():
                    print(f"[{self.site_name}] Description found using class 'description__text'. Length: {len(extracted_description_text)}")
                else:
                    extracted_description_text = None # Reset if empty
                    print(f"[{self.site_name}] Description 'description__text' element found, but no text content.")
            else:
                print(f"[{self.site_name}] Description element with class 'description__text' not found.")

        # Method 3: class 'ogl__description' (another common class)
        if not extracted_description_text:
            description_div_ogl_class = soup.find('div', class_='ogl__description')
            if description_div_ogl_class:
                paragraphs = description_div_ogl_class.find_all('p')
                if paragraphs:
                    extracted_description_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else:
                    extracted_description_text = description_div_ogl_class.get_text(separator="\n", strip=True)

                if extracted_description_text and extracted_description_text.strip():
                    print(f"[{self.site_name}] Description found using class 'ogl__description'. Length: {len(extracted_description_text)}")
                else:
                    extracted_description_text = None # Reset if empty
                    print(f"[{self.site_name}] Description 'ogl__description' element found, but no text content.")
            else:
                print(f"[{self.site_name}] Description element with class 'ogl__description' not found.")

        # Method 4: class 'description__rolled' (fallback)
        if not extracted_description_text:
            description_div_rolled_class = soup.find('div', class_='description__rolled')
            if description_div_rolled_class:
                paragraphs = description_div_rolled_class.find_all('p')
                if paragraphs:
                    extracted_description_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else:
                    extracted_description_text = description_div_rolled_class.get_text(separator="\n", strip=True)
                
                if extracted_description_text and extracted_description_text.strip():
                    print(f"[{self.site_name}] Description found using class 'description__rolled'. Length: {len(extracted_description_text)}")
                else:
                    extracted_description_text = None # Reset if empty
                    print(f"[{self.site_name}] Description 'description__rolled' element found, but no text content.")
            else:
                print(f"[{self.site_name}] Description element with class 'description__rolled' not found.")

        # Method 5: class 'description' (generic fallback)
        if not extracted_description_text:
            description_div_generic_class = soup.find('div', class_='description')
            if description_div_generic_class:
                paragraphs = description_div_generic_class.find_all('p')
                if paragraphs:
                    extracted_description_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else:
                    extracted_description_text = description_div_generic_class.get_text(separator="\n", strip=True)

                if extracted_description_text and extracted_description_text.strip():
                    print(f"[{self.site_name}] Description found using generic class 'description'. Length: {len(extracted_description_text)}")
                else:
                    extracted_description_text = None # Reset if empty
                    print(f"[{self.site_name}] Description generic 'description' element found, but no text content.")
            else:
                print(f"[{self.site_name}] Description element with generic class 'description' not found.")

        # Extract all features from all 'features__container' divs
        all_features_list = []
        features_containers = soup.find_all('div', class_='features__container')
        print(f"[{self.site_name}] Found {len(features_containers)} 'features__container' divs for detailed features.")

        for i, container in enumerate(features_containers):
            print(f"[{self.site_name}] Processing features_container #{i+1}")
            # Try to get features from <ul><li> structure
            ul_element = container.find('ul', class_='features__list-2') # Specific to one type of container
            if not ul_element: # More generic ul search if the specific one is not found
                ul_element = container.find('ul')

            if ul_element:
                list_items = ul_element.find_all('li', recursive=False)
                print(f"[{self.site_name}] Container #{i+1} (ul): Found {len(list_items)} li elements.")
                for li_item in list_items:
                    name_tag = li_item.find('span', class_='features__item_name')
                    value_tag = li_item.find('span', class_='features__item_value')
                    if name_tag and value_tag:
                        name = name_tag.get_text(strip=True)
                        value = value_tag.get_text(strip=True)
                        if name and value: # Ensure both name and value have content
                            feature_string = f"{name}: {value}"
                            if feature_string not in all_features_list: # Avoid duplicates
                                all_features_list.append(feature_string)
                                print(f"[{self.site_name}] Added feature (ul>li): {feature_string}")
            
            # Try to get features from <dl><dt><dd> structure
            dl_element = container.find('dl')
            if dl_element:
                dt_tags = dl_element.find_all('dt', recursive=False)
                print(f"[{self.site_name}] Container #{i+1} (dl): Found {len(dt_tags)} dt elements.")
                for dt_tag in dt_tags:
                    dd_tag = dt_tag.find_next_sibling('dd') # Assuming dd is always a sibling
                    if dd_tag:
                        name = dt_tag.get_text(strip=True).replace(':', '') # Clean name
                        value = dd_tag.get_text(strip=True)
                        if name and value: # Ensure both name and value have content
                            feature_string = f"{name}: {value}"
                            if feature_string not in all_features_list: # Avoid duplicates
                                all_features_list.append(feature_string)
                                print(f"[{self.site_name}] Added feature (dl>dt): {feature_string}")
            
            if not ul_element and not dl_element:
                 print(f"[{self.site_name}] Container #{i+1}: No ul or dl found for feature extraction in this specific container.")


        # Combine main description (if any) with all extracted features
        final_description_parts = []
        if extracted_description_text and extracted_description_text.strip():
            final_description_parts.append(extracted_description_text)
        
        if all_features_list:
            # Join all collected features into a single string, separated by newlines
            features_section_string = "\n".join(all_features_list)
            
            if final_description_parts: # If there was a main description, add a separator and then features
                final_description_parts.append("\n\nSzczegóły oferty:\n" + features_section_string)
            else: # If no main description, features become the description (with a title)
                # Remove leading newlines from features_section_string if it's the only content
                final_description_parts.append("Szczegóły oferty:\n" + features_section_string)

        if final_description_parts:
            full_description = "\n".join(filter(None, final_description_parts)) # Ensure no empty strings from list join
            details['description'] = full_description[:1000] + '...' if len(full_description) > 1000 else full_description
        
        # Log final description status
        if details['description'] != 'N/A':
            print(f"[{self.site_name}] Final Description assigned. Length: {len(details['description'])}, Preview: {details['description'][:100]}")
        else:
            print(f"[{self.site_name}] Final Description: N/A (no method yielded content, including additional info).")

        # Image count
        # Look for a container with class 'js-gallery__container'
        gallery_container = soup.find(class_='js-gallery__container')
        if gallery_container:
            # Count all 'img' tags within this container
            details['image_count'] = len(gallery_container.find_all('img'))
        else:
            # Fallback to the old method if 'js-gallery__container' is not found
            gallery = soup.find('div', class_='gallery')
            if gallery:
                details['image_count'] = len(gallery.find_all('img'))
            else:
                details['image_count'] = 0
        print(f"[{self.site_name}] Image count: {details['image_count']}")

        # First image URL from details page
        details['first_image_url'] = None
        # Try to find the main image in a gallery container
        gallery_big_photo_container = soup.find(class_=['gallery__big-photo-container', 'photo-container']) # Common classes for main image
        if gallery_big_photo_container:
            img_tag = gallery_big_photo_container.find('img')
            if img_tag and img_tag.get('src'):
                details['first_image_url'] = img_tag['src']
                print(f"[{self.site_name}] Found first_image_url in gallery__big-photo-container: {details['first_image_url']}")

        # Fallback if not found in the primary gallery container, try js-gallery__container (used for count)
        if not details['first_image_url'] and gallery_container: # gallery_container is from image_count section
            img_tag = gallery_container.find('img') # First image in this container
            if img_tag and img_tag.get('src'):
                details['first_image_url'] = img_tag['src']
                print(f"[{self.site_name}] Found first_image_url in js-gallery__container: {details['first_image_url']}")
        
        # Fallback to any prominent image if specific containers fail
        if not details['first_image_url']:
            # Look for an image within an element that might be a main image wrapper
            # e.g., a div with class 'photo' or 'image' or an article tag
            main_content_areas = soup.find_all(['article', 'div'], class_=['photo', 'image', 'gallery', 'slick-current', 'fotorama__active'], limit=5)
            for area in main_content_areas:
                img_tag = area.find('img')
                if img_tag and img_tag.get('src'):
                    # Avoid tiny icons by checking for typical data-src or larger src if possible
                    # This is a heuristic; actual image size/relevance check is complex without rendering
                    src_val = img_tag.get('data-src', img_tag.get('src'))
                    if src_val: # Ensure src_val is not None
                        details['first_image_url'] = src_val
                        print(f"[{self.site_name}] Found first_image_url in a fallback area: {details['first_image_url']}")
                        break # Found one, stop searching

        if details.get('first_image_url') and details['first_image_url'].startswith('//'):
            details['first_image_url'] = f"https:{details['first_image_url']}"
        elif details.get('first_image_url') and not details['first_image_url'].startswith('http'):
            # Assuming it's a relative path, prepend base_url if available
            # This part needs self.base_url to be set correctly for the site
            # For Domiporta, base_url is set in fetch_listings_page.
            # If parse_listing_details is called independently, this might need adjustment.
            if hasattr(self, 'base_url') and self.base_url:
                 details['first_image_url'] = f"{self.base_url}{details['first_image_url'] if details['first_image_url'].startswith('/') else '/' + details['first_image_url']}"
                 print(f"[{self.site_name}] Prepended base_url to relative first_image_url: {details['first_image_url']}")
            else:
                print(f"[{self.site_name}] Warning: first_image_url is relative but self.base_url is not available. Path: {details['first_image_url']}")


        # Additional details
        details_table = soup.find('table', class_='parameters')
        if details_table:
            for row in details_table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).replace(':', '')
                    value = cells[1].get_text(strip=True)
                    details[key] = value

        print(f"[{self.site_name}] Parsed details for: {details.get('title', 'N/A')[:30]}...")
        return details
