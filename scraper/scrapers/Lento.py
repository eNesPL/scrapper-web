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
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Lento.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        # Using the provided example URL with pagination
        example_url = f"https://gliwice.lento.pl/nieruchomosci/mieszkania/sprzedaz.html?price_from=50000&price_to=300000&atr_1_from=20&atr_2_in%5B0%5D=2&atr_2_in%5B1%5D=3&page={page}"
        
        print(f"[{self.site_name}] Fetching listings page {page} using URL: {example_url} (Criteria: {search_criteria})")
        
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

        # Simple check for next page - look for pagination next button
        next_button = soup.find('a', class_='next')
        has_next_page = next_button is not None and 'disabled' not in next_button.get('class', [])
        
        return listings, has_next_page

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


        # Description - new approach using specified XPath
        description_text_from_xpath = None
        if lxml_html and html_content:
            try:
                if 'tree' not in locals() or tree is None: # Ensure tree is parsed
                    tree = lxml_html.fromstring(html_content)
                
                # XPath provided by user for the main description container
                description_container_xpath = '/html/body/main/div[2]/div[2]/div/div/div[1]/div[1]/div[9]'
                description_elements = tree.xpath(description_container_xpath)

                if description_elements:
                    print(f"[{self.site_name}] DEBUG: Found description container with XPath: {description_container_xpath}")
                    container_element = description_elements[0]
                    
                    # Attempt to reformat content within the container
                    # Prioritize list items, then paragraphs, then general text content
                    lines = []
                    # Check for <ul> -> <li> structure
                    ul_tags = container_element.xpath('.//ul') # Find all ul descendants
                    processed_li = False
                    for ul in ul_tags:
                        li_tags = ul.xpath('./li') # Find direct li children of this ul
                        for li in li_tags:
                            line_text = li.text_content().strip()
                            if line_text:
                                lines.append(line_text)
                                processed_li = True
                        if processed_li and ul_tags.index(ul) < len(ul_tags) -1 : # Add a separator between multiple ULs
                            lines.append("---")


                    # If no <li> items were processed, try <p> tags
                    if not processed_li:
                        p_tags = container_element.xpath('.//p') # Find all p descendants
                        for p_tag in p_tags:
                            line_text = p_tag.text_content().strip()
                            if line_text:
                                lines.append(line_text)
                    
                    # If still no lines, get all text content from the container
                    if not lines:
                        full_text_content = container_element.text_content()
                        # Split by newlines that might exist in the raw text, then strip each line
                        raw_lines = full_text_content.split('\n')
                        for raw_line in raw_lines:
                            stripped_line = raw_line.strip()
                            if stripped_line: # Add only non-empty lines
                                lines.append(stripped_line)
                    
                    if lines:
                        description_text_from_xpath = "\n".join(lines)
                        print(f"[{self.site_name}] DEBUG: Extracted and reformatted description from XPath. Length: {len(description_text_from_xpath)}, Preview: '{description_text_from_xpath[:200]}...'")
                    else:
                        print(f"[{self.site_name}] DEBUG: Description container at XPath found, but no text content extracted after formatting attempts.")
                else:
                    print(f"[{self.site_name}] DEBUG: Description container NOT found with XPath: {description_container_xpath}")

            except Exception as e:
                print(f"[{self.site_name}] Error extracting or reformatting description with XPath: {e}")
        else:
            print(f"[{self.site_name}] lxml not available or HTML content missing, cannot use XPath for description.")

        # Assign to details['description']
        if description_text_from_xpath and description_text_from_xpath.strip():
            details['description'] = description_text_from_xpath[:1000] + '...' if len(description_text_from_xpath) > 1000 else description_text_from_xpath
        else:
            # Fallback to original "Szczegóły ogłoszenia" if XPath fails and if that logic is still desired
            # For now, if XPath fails, it will be N/A as per user's focus on the XPath.
            # If a more complex fallback is needed, the old logic for 'oglDetails' and 'Opis oferty' header could be reinstated here.
            print(f"[{self.site_name}] DEBUG: Description from XPath is empty or None. Setting to N/A.")
            details['description'] = 'N/A' # Explicitly N/A if XPath method fails to yield content

        # Log final description status
        if details['description'] != 'N/A':
            print(f"[{self.site_name}] Final Description assigned. Length: {len(details['description'])}, Preview: {details['description'][:100]}")
        else:
            print(f"[{self.site_name}] Final Description: N/A (XPath method did not yield content or lxml was unavailable).")


        # Area extraction - keeping existing XPath and fallback logic
        # Ensure 'tree' is available if lxml_html is True
        if lxml_html and html_content and ('tree' not in locals() or tree is None):
            try:
                tree = lxml_html.fromstring(html_content)
            except Exception as e:
                print(f"[{self.site_name}] Error re-parsing HTML with lxml for Area: {e}")
                # tree will remain None or as it was, potentially causing issues for subsequent XPath if not handled
        
        if lxml_html and 'tree' in locals() and tree is not None: # Check if tree was successfully parsed
            try:
                area_elements = tree.xpath('/html/body/main/div[2]/div[2]/div/div/div[1]/div[1]/div[9]/ul/li[2]/span[2]')
                if area_elements:
                    details['area_m2'] = area_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Area (XPath): {details['area_m2']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting area with XPath: {e}. Falling back to BeautifulSoup.")
        
        if details['area_m2'] == 'N/A': # Fallback for area
            details_section_for_area = soup.find('div', class_='oglDetails')
            if details_section_for_area:
                area_items = details_section_for_area.find_all(['li', 'div'], string=re.compile(r'Powierzchnia:', re.IGNORECASE))
                for item in area_items:
                    area_match = re.search(r'Powierzchnia:\s*([\d,.]+\s*m2)', item.get_text(strip=True), re.IGNORECASE)
                    if area_match:
                        details['area_m2'] = area_match.group(1).strip()
                        print(f"[{self.site_name}] Area (BeautifulSoup fallback from details list): {details['area_m2']}")
                        break 
            if details['area_m2'] == 'N/A':
                 print(f"[{self.site_name}] Area not found by XPath or in oglDetails list. Current value: {details['area_m2']}")
            else:
                print(f"[{self.site_name}] Area after all attempts: {details['area_m2']}")


        # Image count and First Image URL
        # Try multiple approaches to get images
        details['image_count'] = 0
        details['first_image_url'] = None

        # Approach 1: Check preview-gallery data attribute
        preview_gallery = soup.find('div', id='preview-gallery')
        if preview_gallery and preview_gallery.get('data-imgcnt'):
            try:
                details['image_count'] = int(preview_gallery['data-imgcnt'])
                print(f"[{self.site_name}] Image count from data-imgcnt: {details['image_count']}")
            except ValueError:
                pass

        # Approach 2: Check thumbnails gallery
        if details['image_count'] == 0:
            thumbnails_gallery = soup.find('div', id='thumbnails-gallery')
            if thumbnails_gallery:
                image_links = thumbnails_gallery.find_all('a', href=True)
                details['image_count'] = len(image_links)
                print(f"[{self.site_name}] Image count from thumbnails-gallery: {details['image_count']}")

        # Approach 3: Check gallery counter
        if details['image_count'] == 0:
            gallery_indicator = soup.find('div', class_='counter')
            if gallery_indicator:
                indicator_text = gallery_indicator.get_text(strip=True)
                match = re.search(r'\d+\s*/\s*(\d+)', indicator_text)
                if match:
                    details['image_count'] = int(match.group(1))
                    print(f"[{self.site_name}] Image count from counter: {details['image_count']}")

        # Get first image URL from multiple possible sources
        img_src = None
        # Source 1: Check for images with class "width-100"
        img_tag = soup.find('img', class_='width-100')
        if img_tag:
            img_src = img_tag.get('src') or img_tag.get('data-src')
            if not img_src:
                picture_tag = img_tag.find_parent('picture')
                if picture_tag:
                    source_tag = picture_tag.find('source')
                    if source_tag:
                        img_src = source_tag.get('srcset')
        
        # Source 2: Check big-img container
        if not img_src:
            big_img_div = soup.find('div', id='big-img')
            if big_img_div:
                img_tag = big_img_div.find('img')
                if img_tag:
                    img_src = img_tag.get('src') or img_tag.get('data-src')
        
        # Source 3: Check mobile gallery
        if not img_src:
            mobile_gallery = soup.find('div', id='mobile-gallery')
            if mobile_gallery:
                img_tag = mobile_gallery.find('img')
                if img_tag:
                    img_src = img_tag.get('src') or img_tag.get('data-lazy') or img_tag.get('data-src')
        
        # Source 4: Check thumbnails gallery
        if not img_src:
            thumbnails_gallery = soup.find('div', id='thumbnails-gallery')
            if thumbnails_gallery:
                first_thumbnail = thumbnails_gallery.find('a', href=True)
                if first_thumbnail:
                    img_src = first_thumbnail.get('href')
        
        # Process found image source
        if img_src:
            if img_src.startswith('//'):
                details['first_image_url'] = f"https:{img_src}"
            elif not img_src.startswith('http'):
                details['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
            else:
                details['first_image_url'] = img_src
            print(f"[{self.site_name}] Found main image: {details['first_image_url']}")

        # If we have first image but count is still 0, set to at least 1
        if details['first_image_url'] and details['image_count'] == 0:
            details['image_count'] = 1

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
