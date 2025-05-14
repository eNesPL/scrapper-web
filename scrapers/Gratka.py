import requests
from bs4 import BeautifulSoup
try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class GratkaScraper(BaseScraper):
    """
    Scraper for Gratka.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Gratka.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.base_url = "https://gratka.pl"
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania

    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page from Gratka.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :return: HTML content (str) or None.
        """
        # Example URL provided by user, in a real scenario, build this from search_criteria
        # For now, we'll use the provided static URL for Gliwice.
        # We can enhance this later to use search_criteria if needed.
        example_url = "https://gratka.pl/nieruchomosci/mieszkania/3-pokojowe/gliwice?cena-calkowita:max=300000&location%5Bmap%5D=1&location%5Bmap_bounds%5D=50.3752324,18.7546442:50.2272469,18.5445885&ogloszenie-zawiera%5B0%5D=zdjecie&ogloszenie-zawiera%5B1%5D=cena&powierzchnia-w-m2:min=25&sort=relevance"
        
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
        :return: Tuple of (listings_summaries, has_next_page) where:
                 - listings_summaries: List of dicts with at least 'url', 'title', 'price'
                 - has_next_page: bool, True if there are more pages to scrape
        """
        print(f"[{self.site_name}] Parsing listings page content.")
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Try finding listings by class 'card' first
        listing_elements = soup.find_all(class_='card')
        
        if not listing_elements:
            # Fallback to <article class="teaserUnified">
            print(f"[{self.site_name}] No elements with class 'card' found. Trying 'article.teaserUnified'.")
            listing_elements = soup.find_all('article', class_='teaserUnified')
        
        if not listing_elements:
            # Fallback to data-testid="listing-item"
            print(f"[{self.site_name}] No elements with 'article.teaserUnified' found. Trying 'data-testid=listing-item'.")
            listing_elements = soup.find_all(attrs={"data-testid": "listing-item"})

        print(f"[{self.site_name}] Found {len(listing_elements)} potential listing elements using combined methods.")

        for item_element in listing_elements:
            summary = {}
            
            # URL and Title
            # Title is often in <a class="teaserUnified__anchor" href="..."> or similar
            link_tag = item_element.find('a', class_='teaserUnified__anchor')
            if not link_tag: # Fallback for data-testid items
                link_tag = item_element.find('a', href=True) 

            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                if not url.startswith('http'):
                    summary['url'] = f"{self.base_url}{url if url.startswith('/') else '/' + url}"
                else:
                    summary['url'] = url
                
                # Try to get title from a specific element or the link text itself
                title_tag = link_tag.find('h2', class_='teaserUnified__title') # Common pattern
                if title_tag:
                    summary['title'] = title_tag.get_text(strip=True)
                elif link_tag.get_text(strip=True): # Fallback to link's text
                     summary['title'] = link_tag.get_text(strip=True)
                else: # Try another common title pattern
                    title_span = link_tag.find('span', class_='teaserHeading__mainText')
                    if title_span:
                        summary['title'] = title_span.get_text(strip=True)
                    else:
                        summary['title'] = 'N/A'
            else:
                print(f"[{self.site_name}] Skipping item, no URL found.")
                continue

            # Price
            # Price is often in <p class="priceInfo__value"> or similar structure
            price_tag = item_element.find('p', class_='priceInfo__value')
            if price_tag:
                summary['price'] = price_tag.get_text(strip=True)
            else: # Fallback for other price structures
                price_span = item_element.find('span', attrs={"data-testid": "price"})
                if price_span:
                    summary['price'] = price_span.get_text(strip=True)
                else:
                    summary['price'] = 'N/A'
            
            if summary.get('url'): # Ensure we have a URL before adding
                listings.append(summary)
                print(f"[{self.site_name}] Parsed summary: Title: {summary.get('title', 'N/A')[:30]}..., Price: {summary.get('price', 'N/A')}, URL: {summary.get('url')}")

        # Simple check for next page - look for pagination next button
        soup = BeautifulSoup(html_content, 'html.parser')
        next_button = soup.find('a', class_='pagination__next')
        has_next_page = next_button is not None and 'disabled' not in next_button.get('class', [])
        
        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Gratka.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        try:
            response = requests.get(listing_url, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
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

        details = {
            'title': 'N/A',
            'price': 'N/A',
            'area_m2': 'N/A',
            'description': 'N/A',
            'image_count': 0,
            'first_image_url': None
        }
        
        soup = BeautifulSoup(html_content, 'html.parser')
        lxml_tree = None
        if lxml_html:
            try:
                lxml_tree = lxml_html.fromstring(html_content)
            except Exception as e:
                print(f"[{self.site_name}] Error parsing HTML with lxml: {e}")
                lxml_tree = None # Ensure it's None if parsing fails

        # --- Extract data using XPath if lxml_tree is available ---
        if lxml_tree is not None:
            try:
                # Price
                price_elements = lxml_tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/div[1]/div/span[1]')
                if price_elements:
                    details['price'] = price_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Price (XPath): {details['price']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting price with XPath: {e}")

            try:
                # Area
                area_elements = lxml_tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/div[2]/span[2]/span')
                if area_elements:
                    details['area_m2'] = area_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Area (XPath): {details['area_m2']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting area with XPath: {e}")

            floor_info_for_description = None
            try:
                # Floor (for description)
                floor_elements = lxml_tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/div[2]/span[3]/span')
                if floor_elements:
                    floor_info_for_description = floor_elements[0].text_content().strip()
                    print(f"[{self.site_name}] Floor info (XPath): {floor_info_for_description}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting floor with XPath: {e}")

            # First image URL using XPath to the button
            try:
                # XPath points to a button, image might be inside or as background
                button_elements = lxml_tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[3]/div[1]/button[1]')
                if button_elements:
                    button_element = button_elements[0]
                    # Try to find an <img> tag inside the button
                    img_tag_in_button = button_element.find('.//img') # .// searches descendants
                    if img_tag_in_button is not None and img_tag_in_button.get('src'):
                        details['first_image_url'] = img_tag_in_button.get('src')
                        print(f"[{self.site_name}] First image URL (XPath - img in button): {details['first_image_url']}")
                    else:
                        # Try to get from style attribute if it's a background image
                        style_attr = button_element.get('style')
                        if style_attr and 'background-image' in style_attr:
                            import re
                            match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_attr)
                            if match:
                                details['first_image_url'] = match.group(1)
                                print(f"[{self.site_name}] First image URL (XPath - button style): {details['first_image_url']}")
                if details.get('first_image_url') and details['first_image_url'].startswith('//'):
                    details['first_image_url'] = f"https:{details['first_image_url']}"
                elif details.get('first_image_url') and not details['first_image_url'].startswith('http'):
                     details['first_image_url'] = f"{self.base_url}{details['first_image_url'] if details['first_image_url'].startswith('/') else '/' + details['first_image_url']}"

            except Exception as e:
                print(f"[{self.site_name}] Error extracting first image with XPath: {e}")
        else:
            print(f"[{self.site_name}] lxml not available or HTML parsing failed, skipping XPath extractions.")

        # --- Extract data using BeautifulSoup ---
        
        # Title (using a common h1 tag or title tag)
        title_tag_h1 = soup.find('h1')
        if title_tag_h1:
            details['title'] = title_tag_h1.get_text(strip=True)
        else:
            title_tag_head = soup.find('title')
            if title_tag_head:
                details['title'] = title_tag_head.get_text(strip=True)
        print(f"[{self.site_name}] Title (BeautifulSoup): {details['title']}")

        # Description parts
        description_parts = []
        
        # Main description (e.g., from itemprop or a common class)
        main_desc_element = soup.find(attrs={"itemprop": "description"})
        if not main_desc_element: # Fallback to a common class if itemprop not found
            main_desc_element = soup.find('div', class_='description__text') # Example class
        if main_desc_element:
            main_desc_text = main_desc_element.get_text(separator="\n", strip=True)
            if main_desc_text:
                description_parts.append(main_desc_text)
                print(f"[{self.site_name}] Main description found (BeautifulSoup). Length: {len(main_desc_text)}")

        # Add floor info to description if found
        if floor_info_for_description:
            description_parts.append(f"Piętro: {floor_info_for_description}")

        # Features from <ul data-v-0e98df09="" class="Akny2O">
        features_ul = soup.find('ul', class_='Akny2O', attrs={'data-v-0e98df09': True})
        if not features_ul: # Fallback if data-v attribute is not exactly matched or not present
             features_ul = soup.find('ul', class_='Akny2O')

        if features_ul:
            feature_items = []
            for li_tag in features_ul.find_all('li', class_='_9-I1E2', attrs={'data-cy': 'tagItem'}):
                feature_text = li_tag.get_text(strip=True)
                if feature_text:
                    feature_items.append(feature_text)
            if feature_items:
                description_parts.append("Dodatkowe cechy:\n- " + "\n- ".join(feature_items))
                print(f"[{self.site_name}] Found features (ul.Akny2O): {', '.join(feature_items)}")
        else:
            print(f"[{self.site_name}] Features list (ul.Akny2O) not found.")
            
        # Combine description parts
        if description_parts:
            full_description = "\n\n".join(filter(None, description_parts))
            details['description'] = full_description[:1000] + '...' if len(full_description) > 1000 else full_description
        
        # Image count
        # Try to find a specific gallery container
        # Common classes for main gallery on Gratka: galleryDesktop__container, galleryViewer, listingGallery
        gallery_container = soup.find('div', class_=['galleryDesktop__container', 'galleryViewer', 'listingGallery'])
        if gallery_container:
            # Count images directly within this specific gallery container
            images_in_gallery = gallery_container.find_all('img', src=True)
            details['image_count'] = len(images_in_gallery)
            print(f"[{self.site_name}] Image count (gallery container): {details['image_count']}")
            
            # First image URL from the identified gallery container
            if images_in_gallery:
                img_src = images_in_gallery[0].get('src')
                if img_src:
                    if not img_src.startswith('http'):
                        details['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                    else:
                        details['first_image_url'] = img_src
        else:
            # Fallback if specific gallery container is not found - try to count images in main content
            # This is less precise and might overcount.
            main_content = soup.find('main') 
            if main_content:
                all_images_in_main = main_content.find_all('img', src=True)
                details['image_count'] = len(all_images_in_main)
                # Try to get the first image from main content as a fallback
                if all_images_in_main and not details['first_image_url']:
                    img_src = all_images_in_main[0].get('src')
                    if img_src:
                        if not img_src.startswith('http'):
                             details['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                        else:
                            details['first_image_url'] = img_src
            print(f"[{self.site_name}] Image count (fallback - main content): {details['image_count']}")
        
        print(f"[{self.site_name}] First image URL (BeautifulSoup): {details['first_image_url']}")


        # --- Attempt to extract Area using BeautifulSoup as a fallback or primary if XPath failed ---
        if details['area_m2'] == 'N/A' or not lxml_tree: # If XPath failed or lxml not available
            print(f"[{self.site_name}] Attempting to extract area using BeautifulSoup.")
            # Common pattern: parameters are often in a list or divs.
            # Look for a span/div containing "m²" or near a label "Powierzchnia"
            # This is a generic example, Gratka's structure might vary.
            # Example: <div class="parameters__value"><span>55 m²</span></div>
            # Example: <li><span>Powierzchnia</span><span>55 m²</span></li>
            
            # Try finding a parameter list/section first
            parameters_section = soup.find('div', class_=['parameters', 'listingAttributes', 'details_param', 'summaryTable']) # Common class names, added summaryTable
            if parameters_section:
                # Try to find a label "Powierzchnia" and get its value
                area_label_tag = parameters_section.find(lambda tag: tag.name in ['span', 'div', 'dt', 'th'] and "Powierzchnia" in tag.get_text() and "całkowita" not in tag.get_text()) # Avoid "Powierzchnia całkowita" if it's different
                if area_label_tag:
                    value_tag = area_label_tag.find_next_sibling(['span', 'div', 'dd', 'td'])
                    if value_tag and "m²" in value_tag.get_text():
                        area_text_bs = value_tag.get_text(strip=True)
                        details['area_m2'] = area_text_bs
                        print(f"[{self.site_name}] Area (BeautifulSoup - label 'Powierzchnia'): {details['area_m2']}")

                # If label search fails, try direct search for "m²" within the section
                if details['area_m2'] == 'N/A':
                    area_tag_bs = parameters_section.find(lambda tag: tag.name in ['span', 'div', 'li', 'dd', 'td'] and "m²" in tag.get_text() and "Cena za m²" not in tag.get_text())
                    if area_tag_bs:
                        area_text_bs = area_tag_bs.get_text(strip=True)
                        if ":" in area_text_bs: # Simple cleaning if it's like "Label: Value"
                            area_text_bs = area_text_bs.split(":")[-1].strip()
                        details['area_m2'] = area_text_bs
                        print(f"[{self.site_name}] Area (BeautifulSoup - parameters section, m² search): {details['area_m2']}")
            
            if details['area_m2'] == 'N/A': # If still not found, try a more general page-wide search for text with m²
                area_tag_direct = soup.find(lambda tag: tag.name in ['span', 'div'] and "m²" in tag.get_text() and "Cena za m²" not in tag.get_text() and len(tag.get_text(strip=True)) < 30 and len(tag.find_all()) < 3) # Avoid long description texts and complex tags
                if area_tag_direct:
                    area_text_direct = area_tag_direct.get_text(strip=True)
                    if ":" in area_text_direct: 
                        area_text_direct = area_text_direct.split(":")[-1].strip()
                    details['area_m2'] = area_text_direct
                    print(f"[{self.site_name}] Area (BeautifulSoup - direct page m² search): {details['area_m2']}")
        
        # Ensure essential fields are not None before returning, as per BaseScraper expectations
        details.setdefault('title', 'N/A')
        details.setdefault('price', 'N/A')
        details.setdefault('description', 'N/A')
        details.setdefault('image_count', 0)
        details.setdefault('area_m2', 'N/A')
        # first_image_url can be None

        print(f"[{self.site_name}] Parsed details: Price='{details['price']}', Area='{details['area_m2']}', Title='{details['title'][:30]}...'")
        return details
