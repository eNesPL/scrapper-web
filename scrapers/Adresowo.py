import requests
from bs4 import BeautifulSoup
import re
from .base_scraper import BaseScraper

class AdresowoScraper(BaseScraper):
    """
    Scraper for Adresowo.pl real estate listings.
    Note: Adresowo.pl may have cookie consent banners or other mechanisms
    that can alter the HTML content received by simple `requests.get()`.
    If parsing fails, especially for price/images, this might be the cause.
    Consider using a session object to handle cookies or a browser automation
    tool like Selenium if issues persist.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Adresowo.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.base_url = "https://adresowo.pl"
        # Using the hardcoded URL as requested for fetching listings
        self.hardcoded_listings_url = "https://adresowo.pl/f/mieszkania/gliwice/a25_ff0f1p2_p-30"

    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page from Adresowo.pl
        using a hardcoded URL.
        :param search_criteria: dict, search parameters (ignored for this scraper).
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching listings page: {self.hardcoded_listings_url}")
        try:
            # Standard headers to mimic a browser visit, can be expanded if needed
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8', # Added accept-language
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            }
            # Using a session might help with cookie persistence if the site requires it
            # s = requests.Session()
            # response = s.get(self.hardcoded_listings_url, headers=headers, timeout=15)
            response = requests.get(self.hardcoded_listings_url, headers=headers, timeout=15)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.text
        except requests.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page {self.hardcoded_listings_url}: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        It collects sections with class 'search-results__item' until a div
        with class 'search-block-similar' is found.
        :param html_content: str, HTML content of the listings page.
        :return: List of dictionaries, each with at least a 'url', 'title', 'price', and 'area_m2'.
        """
        if not html_content:
            print(f"[{self.site_name}] No HTML content to parse for listings.")
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Find all tags that are either a listing item or the stopper div, in document order.
        all_relevant_tags = soup.find_all(
            lambda tag: (tag.name == 'section' and 'search-results__item' in tag.get('class', [])) or \
                        (tag.name == 'div' and 'search-block-similar' in tag.get('class', []))
        )
        
        print(f"[{self.site_name}] Found {len(all_relevant_tags)} relevant tags (listing items or stopper) to process.")

        collected_listing_sections = []
        for tag in all_relevant_tags:
            # Check if the current tag is the stopper div
            if tag.name == 'div' and 'search-block-similar' in tag.get('class', []):
                print(f"[{self.site_name}] Encountered 'search-block-similar' div, stopping collection of listing sections.")
                break  # Stop processing further tags
            
            # If it's not the stopper, the lambda ensures it's a 'section' with 'search-results__item'.
            collected_listing_sections.append(tag)
        
        print(f"[{self.site_name}] Collected {len(collected_listing_sections)} listing sections before encountering stopper.")

        for section in collected_listing_sections:
            url_suffix = section.get('data-href')
            if not url_suffix:
                # Fallback: try to find an <a> tag with the link within the section
                link_tag = section.find('a', href=re.compile(r'^/o/'))
                if link_tag:
                    url_suffix = link_tag.get('href')

            if not url_suffix:
                # print(f"[{self.site_name}] Skipping a section, no URL suffix found.")
                continue
            
            full_url = self.base_url + url_suffix

            title = 'N/A'
            # Selectors for title might need adjustment based on the internal structure of 'search-results__item'
            title_tag_h2 = section.select_one('div.title-container a.title h2, div.title-container h2.title a, h2.offer-title a, a.title h2') 
            if title_tag_h2:
                title = title_tag_h2.get_text(strip=True)
            else: 
                title_link_tag = section.select_one('a.title, a.isFavouriteEnabled') 
                if title_link_tag:
                    title_attr = title_link_tag.get('title', '').strip()
                    if title_attr:
                        title = title_attr
                    else: 
                        title = title_link_tag.get_text(strip=True)
                        if not title: 
                           h2_inside = title_link_tag.find('h2')
                           if h2_inside: title = h2_inside.get_text(strip=True)

            price = 'N/A'
            area_m2 = 'N/A'

            # Iterate over all 'div' elements with 'role="row"' within the listing section
            for row_div in section.find_all('div', attrs={'role': 'row'}):
                # Get all text pieces within this div, join them for keyword searching
                div_texts = list(row_div.stripped_strings)
                div_full_text = " ".join(div_texts)

                # Try to extract Price
                if 'Cena' in div_full_text:
                    price_span = row_div.find('span', class_='offer-summary__value')
                    if price_span:
                        price_text = price_span.get_text(strip=True)
                        # Find the parent div and get all text after price span
                        price_and_currency = ''
                        for sibling in price_span.next_siblings:
                            if isinstance(sibling, str):
                                price_and_currency += sibling.strip()
                        # If price is digits-only and currency is separate
                        if price_text.replace(' ', '').isdigit() and 'zł' in price_and_currency:
                            price = f"{price_text.strip()} zł"
                        else:
                            price = price_text.replace('\xa0', ' ').strip()

                # Try to extract Area (m2)
                if 'Powierzchnia' in div_full_text:
                    area_span = row_div.find('span', class_='offer-summary__value')
                    if area_span:
                        # Get all text including siblings that might contain units
                        area_text = area_span.get_text(strip=True)
                        siblings_text = ''.join(s.strip() for s in area_span.next_siblings if isinstance(s, str))
                        full_area_text = f"{area_text}{siblings_text}"
                        
                        # Try to extract area value with potential decimal point/comma
                        area_match = re.search(r'(\d[\d\s]*(?:[.,]\d+)?)\s*(?:m²|m2|m\W*2)?', full_area_text)
                        if area_match:
                            area_m2 = f"{area_match.group(1).replace(',', '.').replace(' ', '')} m²"
                        # Fallback to just the span text if extraction fails
                        elif area_text:
                            area_m2 = f"{area_text} m²"
                        else:
                            area_m2 = 'N/A'
            
            # Extract first image URL if available
            first_image_url = None
            # Try multiple common image selectors used on listing cards
            img_selectors = [
                'img.offer-card-img',
                'img.thumbnail__img',
                'img.picture__img',
                'img[data-lazy]',
                'img[src]',
                'img[data-src]'
            ]
            for selector in img_selectors:
                image_tag = section.select_one(selector)
                if image_tag:
                    first_image_url = image_tag.get('data-src') or image_tag.get('src') or image_tag.get('data-lazy')
                    if first_image_url:
                        # Make relative URLs absolute
                        if first_image_url.startswith('//'):
                            first_image_url = 'https:' + first_image_url
                        elif not first_image_url.startswith(('http://', 'https://')):
                            if first_image_url.startswith('/'):
                                first_image_url = self.base_url + first_image_url
                            else:
                                first_image_url = self.base_url + '/' + first_image_url
                        break

            listing_data = {
                'url': full_url,
                'title': title,
                'price': price,
                'area_m2': area_m2,
                'first_image_url': first_image_url
            }
            listings.append(listing_data)
            
        print(f"[{self.site_name}] Parsed {len(listings)} listings from page based on new criteria.")
        return listings

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Adresowo.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            }
            response = requests.get(listing_url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"[{self.site_name}] Error fetching listing details page {listing_url}: {e}")
            return None

    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        :param html_content: str, HTML content of the listing detail page.
        :return: Dictionary with detailed property info (title, price, description, image_count).
        """
        if not html_content:
            return {}

        soup = BeautifulSoup(html_content, 'html.parser')
        details = {}

        # Title
        title_tag = soup.select_one('header.offerHeader h1[itemprop="name"], h1[itemprop="name"]') # More specific for h1 in header first
        if title_tag:
            details['title'] = title_tag.get_text(strip=True)
        else: # Fallback to OpenGraph title
            og_title = soup.find('meta', property='og:title')
            details['title'] = og_title['content'].strip().replace(" | Adresowo.pl", "") if og_title and og_title.get('content') else 'N/A'
        
        # Price - multiple fallback approaches
        price_text_content = 'N/A'
        
        # Try 1: Look for price in div with "Cena" text
        cena_divs = soup.find_all(lambda tag: tag.name == 'div' and 'Cena' in tag.text)
        for div in cena_divs:
            price_span = div.find('span', class_='offer-summary__value')
            if price_span:
                price_text = price_span.get_text(strip=True).replace('\xa0', ' ')
                currency_text = ''.join(price_span.find_next_siblings(string=True))
                if price_text and any(c.isdigit() for c in price_text):
                    if 'zł' in currency_text and 'zł' not in price_text:
                        price_text_content = f"{price_text} zł"
                    else:
                        price_text_content = price_text
                    break
                    
        # Try 2: Look for price in banners or section headers if first approach failed
        if price_text_content == 'N/A':
            price_banners = soup.select('h2, h3, .priceBox, .price-container')
            for banner in price_banners:
                price_match = re.search(r'(\d[\d\s]*)\s*z[łl]', banner.get_text(), re.IGNORECASE)
                if price_match:
                    price_text_content = f"{price_match.group(1).strip()} zł"
                    break
        else:
            # Fallback to other selectors
            price_container = soup.select_one('aside[role="complementary"] p.price, div.priceBox p.price')
            if price_container:
                strong_tag = price_container.find('strong')
                if strong_tag and strong_tag.get_text(strip=True):
                    price_text_content = strong_tag.get_text(strip=True)
                elif price_container.get_text(strip=True):
                    price_text_content = price_container.get_text(strip=True)
        
        # Attempt 2: itemprop="price" (if previous attempt failed or yielded empty/N/A)
        if price_text_content == 'N/A' or not price_text_content.strip():
            price_itemprop_tag = soup.find(attrs={"itemprop": "price"})
            if price_itemprop_tag:
                temp_price = ''
                if price_itemprop_tag.name == 'meta': # Check if it's a meta tag
                    temp_price = price_itemprop_tag.get('content', '').strip()
                else: # Otherwise, get text from the tag
                    temp_price = price_itemprop_tag.get_text(strip=True)
                
                if temp_price: # If we got a non-empty string
                    price_text_content = temp_price

        # Attempt 3: OpenGraph meta tags (og:price:amount) (if previous attempts failed or yielded empty/N/A)
        if price_text_content == 'N/A' or not price_text_content.strip():
            og_price_amount = soup.find('meta', property='og:price:amount')
            if og_price_amount and og_price_amount.get('content', '').strip():
                price_text_content = og_price_amount['content'].strip()

        # Attempt 4: Broader fallback (generic p.price) (if previous attempts failed or yielded empty/N/A)
        if price_text_content == 'N/A' or not price_text_content.strip():
            price_tag_fallback = soup.select_one('p.price') # Generic p.price
            if price_tag_fallback:
                strong_tag = price_tag_fallback.find('strong')
                if strong_tag and strong_tag.get_text(strip=True):
                    price_text_content = strong_tag.get_text(strip=True)
                elif price_tag_fallback.get_text(strip=True): # Fallback to p's text if strong is missing or empty
                    price_text_content = price_tag_fallback.get_text(strip=True)
        
        # Final processing and assignment
        # Ensure 'N/A' is used if price_text_content is empty, whitespace, or still 'N/A'
        if price_text_content and price_text_content.strip() and price_text_content != 'N/A':
            details['price'] = price_text_content.replace('\xa0', ' ').strip()
        else:
            details['price'] = 'N/A'


        # Area (m2)
        area_text = 'N/A'
        
        # Try to find area in div with "Powierzchnia" text, specifically targeting the structure provided
        # Example structure: <div role="row">...Powierzchnia<br><span class="offer-summary__value">43</span>,10 m²</div>
        
        # Find all divs that might contain "Powierzchnia"
        potential_area_containers = soup.find_all(lambda tag: tag.name == 'div' and 'Powierzchnia' in tag.get_text())

        for container in potential_area_containers:
            # Check if this container directly holds the span.offer-summary__value for area
            area_span = container.find('span', class_='offer-summary__value')
            if area_span and 'Powierzchnia' in container.find(string=True, recursive=False): # Check if "Powierzchnia" is a direct text child before the span
                
                value_part = area_span.get_text(strip=True)
                unit_part = ''
                
                # The unit might be part of the span's next sibling text node
                # or part of the container's text after the span
                if area_span.next_sibling and isinstance(area_span.next_sibling, str):
                    unit_part = area_span.next_sibling.strip()
                
                if value_part and unit_part: # e.g., value_part = "43", unit_part = ",10 m²"
                    # Combine and clean, removing potential extra spaces around comma
                    combined_area = f"{value_part}{unit_part}".replace(" ", "").replace(",", ".")
                    # Ensure m² is present and correctly formatted
                    if 'm²' not in combined_area:
                         # Attempt to re-add m² if it was lost, or if only number was found
                        area_match_val = re.search(r'(\d[\d.,]*)', combined_area)
                        if area_match_val:
                            area_text = f"{area_match_val.group(1).replace(',', '.')} m²"
                        else: # Fallback if regex fails
                            area_text = f"{combined_area} m²" 
                    else: # If m² is already there, just use it
                        area_text = combined_area.replace("m2", "m²") # Normalize to m²
                    break # Found and processed area

            # Fallback for slightly different structures within the container
            elif area_span: # If span is found but "Powierzchnia" is not a direct child text
                # This logic is similar to the original, but scoped within a "Powierzchnia" container
                temp_area_text = area_span.get_text(strip=True)
                temp_area_unit = ''.join(s.strip() for s in area_span.next_siblings if isinstance(s, str))
                
                # Check if the unit is directly after the span
                if 'm²' in temp_area_unit:
                    area_text = f"{temp_area_text}{temp_area_unit}".replace(" ", "").replace(",",".")
                    if 'm²' not in area_text: # Ensure m² is present
                        area_text = f"{area_text.replace('m2','')} m²" # Add m² if missing
                    else:
                        area_text = area_text.replace("m2", "m²")
                    break 
                # If unit is not directly after, but value is numeric, assume m²
                elif re.match(r'^[\d.,\s]+$', temp_area_text):
                    area_text = f"{temp_area_text.replace(' ','').replace(',','.')} m²"
                    break
        
        # Fallback: try to extract from description if not found in dedicated field and still N/A
        if area_text == 'N/A' and 'description' in details and details['description'] != 'N/A':
            area_match_desc = re.search(r'(\d+(?:[.,]\d+)?)\s*m[²2]', details['description'])
            if area_match_desc:
                area_text = f"{area_match_desc.group(1).replace(',', '.')} m²"

        details['area_m2'] = area_text.strip() if area_text != 'N/A' else 'N/A'

        # Description
        description_tag = soup.select_one('div.description[itemprop="description"], section#description div.text') # Added alternative selector
        if description_tag:
            # Remove "Zobacz więcej" or similar buttons/links from description
            for unwanted_tag in description_tag.select('button, a.showMore'):
                unwanted_tag.decompose()
                
            p_tags = description_tag.find_all('p')
            if p_tags:
                description_text = "\n".join(p.get_text(strip=True) for p in p_tags if p.get_text(strip=True))
            else: # Fallback to all text in the div if no <p> tags
                description_text = description_tag.get_text(separator="\n", strip=True)
            details['description'] = description_text
        else:
            details['description'] = 'N/A'
            
        # Image Count
        image_count = 0
        # Try to get count from a specific element like "1 / 14" or "14 zdjęć"
        photo_count_element = soup.select_one('div.photoCount, span.photo-count-format, span.photos-count, div.gallery-counter')
        if photo_count_element:
            count_text = photo_count_element.get_text(strip=True)
            # Try to parse "X / Y" or just "Y" or "Y zdjęć"
            match_xy = re.search(r'(\d+)\s*/\s*(\d+)', count_text) # "X / Y"
            match_y_total = re.search(r'/s*(\d+)', count_text) # "/ Y" (total from X/Y)
            match_y_standalone = re.search(r'^(\d+)', count_text) # "Y" or "Y xxx" (count at the beginning)
            
            if match_xy:
                image_count = int(match_xy.group(2)) # Total count from "X / Y"
            elif match_y_total:
                image_count = int(match_y_total.group(1))
            elif match_y_standalone:
                image_count = int(match_y_standalone.group(1)) # The number found
        
        if image_count == 0:
            # Fallback: Count <img> items in the photo gallery thumbnails or main image area
            gallery_thumbnails = soup.select('div#photoList ul li, ul.photo-thumbs li, div.gallery-thumbnails-list li')
            if gallery_thumbnails:
                image_count = len(gallery_thumbnails)
            else:
                # Fallback: count <img> tags in a general gallery section or main image
                gallery_images = soup.select('img')
                if gallery_images:
                    image_count = len(gallery_images)
        
        details['image_count'] = image_count
        
        # Extract first image URL from details page if not already set
        if 'first_image_url' not in details or not details['first_image_url']:
            img_selectors = [
                '#mainImage[src], #mainImage[data-src]',
                'img.gallery-slider__image[src], img.gallery-slider__image[data-src]',
                'img.photo-gallery__img[src], img.photo-gallery__img[data-src]',
                'img.offer-gallery__img[src], img.offer-gallery__img[data-src]'
            ]
            for selector in img_selectors:
                img_tag = soup.select_one(selector)
                if img_tag:
                    details['first_image_url'] = img_tag.get('data-src') or img_tag.get('src')
                    if details['first_image_url']:
                        # Make relative URLs absolute
                        if details['first_image_url'].startswith('//'):
                            details['first_image_url'] = 'https:' + details['first_image_url']
                        elif not details['first_image_url'].startswith(('http://', 'https://')):
                            if details['first_image_url'].startswith('/'):
                                details['first_image_url'] = self.base_url + details['first_image_url']
                            else:
                                details['first_image_url'] = self.base_url + '/' + details['first_image_url']
                        break

        print(f"[{self.site_name}] Parsed details: Title='{details.get('title', 'N/A')[:30]}...', Price='{details.get('price', 'N/A')}', ImgCount={details.get('image_count', 0)}")
        return details
