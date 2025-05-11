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
        :return: List of dictionaries, each with at least a 'url', 'title', and 'price'.
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

        return listings

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
                area_elements = lxml_tree.xpath('/html/body/div[1]/div[2]/main/div[1]/div[4]/section/div/div[2]/span[2]/span/span')
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
        
        # Image count (example: count images in a gallery)
        gallery_element = soup.find('div', class_='gallery') # Adjust selector as needed
        if gallery_element:
            details['image_count'] = len(gallery_element.find_all('img'))
        else: # Fallback: count all images with src attribute in main content area
            main_content = soup.find('main') # Or a more specific container
            if main_content:
                details['image_count'] = len(main_content.find_all('img', src=True))
        print(f"[{self.site_name}] Image count (BeautifulSoup): {details['image_count']}")

        # First image URL (example: first image in gallery or a prominent image)
        first_img_tag = None
        if gallery_element:
            first_img_tag = gallery_element.find('img', src=True)
        if not first_img_tag and main_content: # Fallback
             first_img_tag = main_content.find('img', src=True)
        
        if first_img_tag:
            img_src = first_img_tag.get('src')
            if img_src:
                if not img_src.startswith('http'):
                    details['first_image_url'] = f"{self.base_url}{img_src if img_src.startswith('/') else '/' + img_src}"
                else:
                    details['first_image_url'] = img_src
        print(f"[{self.site_name}] First image URL (BeautifulSoup): {details['first_image_url']}")

        # Ensure essential fields are not None before returning, as per BaseScraper expectations
        details.setdefault('title', 'N/A')
        details.setdefault('price', 'N/A')
        details.setdefault('description', 'N/A')
        details.setdefault('image_count', 0)
        details.setdefault('area_m2', 'N/A')
        # first_image_url can be None

        print(f"[{self.site_name}] Parsed details: Price='{details['price']}', Area='{details['area_m2']}', Title='{details['title'][:30]}...'")
        return details
