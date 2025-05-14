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
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania
        # Using the hardcoded URL as requested for fetching listings
        self.hardcoded_listings_url = "https://adresowo.pl/f/mieszkania/gliwice/a25_ff0f1p2p3_p-30"

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
                    # Nowe podejście do parsowania z uwzględnieniem pełnego tekstu
                    full_text = ' '.join(row_div.stripped_strings)
                    area_match = re.search(r'Powierzchnia.*?(\d+[\.,]?\d*)\s*(m²|m2)', full_text, re.IGNORECASE)
                    if area_match:
                        area_value = area_match.group(1).replace(',', '.')
                        area_m2 = f"{area_value} {area_match.group(2)}"
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
        
        # Price extraction
        price_text_content = 'N/A'
        # Szukaj diva z klasą offer-summary__item1 zawierającego "Cena"
        price_container = soup.find('div', class_='offer-summary__item1')
        if price_container:
            # Znajdź span z ceną w kontenerze
            price_span = price_container.find('span', class_='offer-summary__value')
            if price_span:
                # Pobierz tekst i następujący bezpośrednio po spanie tekst "zł"
                price_value = price_span.get_text(strip=True)
                currency = price_span.next_sibling.strip() if price_span.next_sibling else 'zł'
                price_text_content = f"{price_value} {currency}"
                    
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
        print(f"[{self.site_name}] Starting area parsing...")
        
        # Szukaj kontenera z danymi technicznymi
        summary_container = soup.find('div', class_='offer-summary__item1')
        area_text = 'N/A'
        if summary_container:
            print(f"[{self.site_name}] Found summary container")
            
            # Przeszukaj wszystkie wiersze w kontenerze
            rows = summary_container.find_all('div', role='row')
            for row in rows:
                row_text = ' '.join(row.stripped_strings)
                
                # Parsowanie powierzchni
                if 'Powierzchnia' in row_text:
                    area_span = row.find('span', class_='offer-summary__value')
                    if area_span:
                        area_value = area_span.get_text(strip=True)
                        unit = area_span.next_sibling.strip() if area_span.next_sibling else 'm²'
                        area_text = f"{area_value} {unit}"
                        print(f"[{self.site_name}] Found area: {area_text}")
                        break
            else:
                print(f"[{self.site_name}] No area found in summary rows")
                area_text = 'N/A'
        else:
            print(f"[{self.site_name}] No summary container found")
            area_text = 'N/A'

        print(f"[{self.site_name}] Preliminary area: {area_text}")

        # Final Fallback: try to extract from description if not found in dedicated field and still N/A
        if area_text == 'N/A':
            # Ensure details['description'] exists and is not 'N/A' before searching
            description_content = details.get('description')
            if description_content and description_content != 'N/A':
                area_match_desc = re.search(r'(\d+(?:[.,]\d+)?)\s*m[²2]', description_content)
                if area_match_desc:
                    area_text = f"{area_match_desc.group(1).replace(',', '.')} m²"

        details['area_m2'] = area_text.strip() if area_text != 'N/A' else 'N/A'

        # Description
        description_list = soup.find('ul', class_='offer-description__summary')
        if description_list:
            # Extract text from each <li> and join with newlines
            description_items = [li.get_text(strip=True) for li in description_list.find_all('li')]
            details['description'] = '\n'.join(description_items)
        else:
            # Fallback to old method if new structure not found
            description_tag = soup.find('div', class_='description')
            if description_tag:
                description_text = '\n'.join(
                    line.strip() 
                    for line in description_tag.stripped_strings 
                    if line.strip()
                )
                details['description'] = description_text
            else:
                details['description'] = 'N/A'
            
        # Image Count
        image_count = 0
        if summary_container:
            print(f"[{self.site_name}] Searching for image count in summary container")
            rows = summary_container.find_all('div', role='row')
            for row in rows:
                row_text = ' '.join(row.stripped_strings)
                print(f"[{self.site_name}] Checking row: {row_text[:50]}...")
                
                if any(keyword in row_text for keyword in ['Zdjęć', 'Zdjęcia', 'Liczba zdjęć']):
                    count_span = row.find('span', class_='offer-summary__value')
                    if count_span:
                        count_text = count_span.get_text(strip=True)
                        print(f"[{self.site_name}] Found count span text: '{count_text}'")
                        try:
                            image_count = int(count_text)
                            print(f"[{self.site_name}] Parsed image count: {image_count}")
                            break
                        except ValueError:
                            print(f"[{self.site_name}] Failed to parse image count from: '{count_text}'")
                    else:
                        # Fallback - search for number in row text
                        num_match = re.search(r'\d+', row_text)
                        if num_match:
                            image_count = int(num_match.group())
                            print(f"[{self.site_name}] Extracted image count from row text: {image_count}")
                            break
            
            # Fallback if not found in summary
            if image_count == 0:
                print(f"[{self.site_name}] Image count not found in summary, checking gallery")
                gallery_images = soup.select('div.offer-gallery img')
                image_count = len(gallery_images)
                print(f"[{self.site_name}] Counted images in gallery: {image_count}")
        
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

        print(f"[{self.site_name}] Parsed details: Title='{details.get('title', 'N/A')[:30]}...', "
              f"Price='{details.get('price', 'N/A')}', "
              f"Area='{details.get('area_m2', 'N/A')}', "
              f"ImgCount={details.get('image_count', 0)}, "
              f"DescChars={len(details.get('description', ''))}")
        return details
