import re
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class OtodomScraper(BaseScraper):
    """
    Scraper for Otodom.pl real estate listings.
    """

    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="Otodom.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        self.MAX_PAGES = 5  # Maksymalna liczba stron do przeszukania
        # self.base_url = "https://www.otodom.pl" # Example base URL

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Otodom.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        import requests
        from fake_useragent import UserAgent
        
        print(f"[{self.site_name}] Fetching listings page {page}")
        
        url = "https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/gliwice?limit=36&ownerTypeSingleSelect=ALL&priceMax=300000&areaMin=25&buildYearMin=1950&roomsNumber=%5BTWO%2CTHREE%5D&by=DEFAULT&direction=DESC&viewType=listing&page={page}"
        
        try:
            headers = {
                'User-Agent': UserAgent(use_cache_server=False).random,
                'Accept-Language': 'pl-PL,pl;q=0.9'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page {page}: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: Tuple of (listings, has_next_page) where:
                 - listings: List of dictionaries, each with at least a 'url'
                 - has_next_page: bool, whether there are more pages to scrape
        """
        from bs4 import BeautifulSoup
        print(f"[{self.site_name}] Parsing listings page content.")
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        for item in soup.find_all('article', {'data-cy': 'listing-item'}):
            # Extract URL
            link = item.find('a', {'data-cy': 'listing-item-link'})
            if not link or not link.get('href'):
                continue
                
            url = link['href']
            if not url.startswith('http'):
                url = f"https://www.otodom.pl{url}"
            
            # Extract title
            title = link.get_text(strip=True)
            
            # Extract price
            price_tag = item.find('span', {'class': 'css-2bt9f1'})
            price = price_tag.get_text(strip=True).replace(' ', '').replace('zł', '').replace(',', '.') if price_tag else None
            
            # Extract area, rooms and other details
            details = {}
            specs_list = item.find('dl', {'class': 'css-9q2yy4'})
            if specs_list:
                for dt, dd in zip(specs_list.find_all('dt'), specs_list.find_all('dd')):
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)
                    if key == 'Liczba pokoi':
                        details['rooms'] = value.split()[0]
                    elif key == 'Powierzchnia':
                        details['area'] = value.replace('m²', '').strip()
                    elif key == 'Piętro':
                        details['floor'] = value
            
            # Extract location
            location = item.find('p', {'class': 'css-42r2ms'})
            
            listing_data = {
                'url': url,
                'title': title,
                'price': price,
                'rooms': details.get('rooms'),
                'area_m2': details.get('area'),
                'floor': details.get('floor'),
                'price_per_m2': details.get('price_per_m2'),
                'location': location.get_text(strip=True) if location else None,
                'site_name': self.site_name
            }
            listings.append(listing_data)
            
        # Check for next page button
        next_page_button = soup.find('a', {'data-cy': 'pagination.next-page'})
        has_next_page = next_page_button is not None and len(listings) > 0
        
        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Otodom.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        try:
            headers = {
                'User-Agent': UserAgent(use_cache_server=False).random,
                'Accept-Language': 'pl-PL,pl;q=0.9',
                'Referer': 'https://www.otodom.pl/'
            }
            response = requests.get(listing_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Sprawdź czy to nie jest strona błędu
            if "Przepraszamy, ale ta strona nie istnieje" in response.text:
                print(f"[{self.site_name}] Page not found: {listing_url}")
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
                 Should include 'price', 'description', 'image_count', 'title'.
        """
        from bs4 import BeautifulSoup
        print(f"[{self.site_name}] Parsing listing details page content.")
        if not html_content:
            return {}

        soup = BeautifulSoup(html_content, 'html.parser')
        details = {}

        # Extract title
        title_tag = soup.find('h1', {'data-cy': 'adPageAdTitle'})
        details['title'] = title_tag.get_text(strip=True) if title_tag else 'N/A'

        # Extract price - multiple potential locations
        price = None
        # Try main price header first
        price_tag = soup.find('strong', {'data-cy': 'adPageHeaderPrice'})
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            price = price_text.replace(' ', '').replace('zł', '').replace(',', '.').strip()
        
        # Fallback to price in description if not found
        if not price:
            price_div = soup.find('div', string=lambda t: t and any(x in t.lower() for x in ['cena', 'price']))
            if price_div:
                price_text = price_div.find_next('div').get_text(strip=True)
                price = price_text.replace(' ', '').replace('zł', '').replace(',', '.').strip()
        
        if price:
            # Clean price string - remove non-numeric chars except dot
            price = ''.join(c for c in price if c.isdigit() or c in ('.', ','))
            # Handle Polish decimal separator
            price = price.replace(',', '.')
            try:
                price = float(price)
                details['price'] = price
            except (ValueError, TypeError):
                details['price'] = None

        # Extract description with better formatting
        description = ''
        
        # Try main description section
        desc_div = soup.find('div', {'data-cy': 'adPageAdDescription'})
        if not desc_div:
            # Try alternative locations
            desc_div = soup.select_one('div[class*="description"], div[class*="css-1shxysy"]')
        
        if desc_div:
            # Clean up description while preserving paragraphs
            description = '\n\n'.join(
                p.get_text().strip() 
                for p in desc_div.find_all(['p', 'div', 'br']) 
                if p.get_text().strip()
            )
            # Remove excessive empty lines
            description = re.sub(r'\n{3,}', '\n\n', description).strip()
        
        # Add property details from the info section
        details_section = soup.find('div', {'data-sentry-component': 'AdDetailsBase'})
        if details_section:
            details_text = []
            for item in details_section.find_all('div', {'class': 'css-1xw0jqp'}):
                items = item.find_all('p', {'class': 'css-1airkmu'})
                if len(items) >= 2:
                    name = items[0].get_text(strip=True).replace(':', '')
                    value = items[1].get_text(strip=True)
                    details_text.append(f"{name}: {value}")
            
            if details_text:
                description = f"{description}\n\nParametry:\n" + '\n'.join(details_text) if description else 'Parametry:\n' + '\n'.join(details_text)
        
        details['description'] = description.strip() if description else 'Brak opisu'

        # Extract parameters from multiple possible sections
        params = {}
        
        # Main parameters section - new structure
        details_container = soup.find('div', {'data-sentry-component': 'AdDetailsBase'})
        if details_container:
            # Extract all parameters from item grids
            for item_grid in details_container.find_all('div', {'class': 'css-1xw0jqp'}):
                items = item_grid.find_all('p', {'class': 'css-1airkmu'})
                if len(items) >= 2:
                    name = items[0].get_text(strip=True).replace(':', '').replace('<!-- -->', '')
                    value = items[1].get_text(strip=True).replace('<!-- -->', '')
                    if name and value:
                        params[name] = value

        # Fallback to old structure if not found
        if not params:
            params_section = soup.find('div', {'data-testid': 'ad.top-information.table'})
            if params_section:
                for row in params_section.find_all('div', {'data-testid': 'table-row'}):
                    cells = row.find_all('div')
                    if len(cells) >= 2:
                        name = cells[0].get_text(strip=True).replace(':', '')
                        value = cells[1].get_text(strip=True)
                        if name and value:
                            params[name] = value

        # Additional parameters from description
        description = soup.find('div', {'data-cy': 'adPageAdDescription'})
        if description:
            desc_text = description.get_text()
            # Extract key details from description text
            if 'powierzchni' in desc_text.lower():
                area_match = re.search(r'(\d+[,.]\d+)\s*m\s*kw', desc_text)
                if area_match:
                    params['Powierzchnia'] = area_match.group(1).replace(',', '.')

        # Extract and standardize important parameters
        def clean_area(area_str):
            if not area_str:
                return None
            try:
                return float(area_str.replace('m²', '').replace(',', '.').strip())
            except (ValueError, TypeError):
                return None

        def clean_rooms(rooms_str):
            if not rooms_str:
                return None
            try:
                return int(rooms_str.split()[0])
            except (ValueError, TypeError):
                return None

        # Try multiple possible parameter names
        details['area_m2'] = clean_area(
            params.get('Powierzchnia') or 
            params.get('Powierzchni') or
            params.get('Metraż')
        )
        details['rooms'] = clean_rooms(
            params.get('Liczba pokoi') or 
            params.get('Liczba pokoji') or
            params.get('Pokoje')
        )
        details['floor'] = params.get('Piętro', 'N/A').split('/')[0].strip()  # Handle format like "parter/2"

        # Extract all images and main image
        image_tags = []
        main_image = None
        
        # Try to get main image from picture tag first
        picture_tag = soup.find('picture', {'data-sentry-component': 'MainImage'})
        if picture_tag:
            img_tag = picture_tag.find('img')
            if img_tag and img_tag.get('src'):
                main_image = img_tag['src'].split(';')[0]  # Remove size parameters
        
        # Try new gallery structure
        gallery_wrapper = soup.find('div', {'data-sentry-component': 'Gallery'})
        if gallery_wrapper:
            # Find all image sources in the gallery
            sources = gallery_wrapper.find_all('source')
            for source in sources:
                if source.get('srcset'):
                    image_url = source['srcset'].split('?')[0]
                    if image_url not in image_tags:
                        image_tags.append({'src': image_url})
            
            # Also check img tags in the gallery
            gallery_images = gallery_wrapper.find_all('img', {'src': True})
            for img in gallery_images:
                if img['src'] not in [t['src'] for t in image_tags]:
                    image_tags.append({'src': img['src']})
        
        # Fallback to old gallery structure
        if not image_tags:
            gallery = soup.find('div', {'data-testid': 'gallery'})
            if not gallery:
                gallery = soup.find('div', {'class': 'css-1g43fk1'})  # Alternative gallery class
                
            if gallery:
                # Try both src and data-src attributes
                image_tags = gallery.find_all('img', {'src': True})
                if not image_tags:
                    image_tags = gallery.find_all('img', {'data-src': True})
                    image_tags = [{'src': img['data-src']} for img in image_tags]
        
        # Final fallback to other image locations
        if not image_tags:
            image_tags = soup.find_all('img', {
                'data-cy': lambda x: x and 'image' in x.lower()
            })
        if not image_tags:
            image_tags = soup.select('img[src*="ireland.apollo.olxcdn.com"]')
        
        # Clean and store all image URLs, filtering out logos
        details['images'] = []
        for img in image_tags:
            src = img.get('src') or img.get('data-src')
            if (src and src.startswith(('http://', 'https://')) 
                and not any(logo_word in src.lower() for logo_word in ['logo', 'agent', 'biuro', 'deweloper', 'remax', 'metrohouse'])
                and 'user' not in src.lower()
                and not src.endswith(('.svg', '.png'))
                and not any(x in src.lower() for x in ['/logos/', '/brands/', '/agents/'])):  # Ignore logo files
                # Clean up image URL - remove size parameters
                clean_src = src.split('?')[0].split(';')[0]
                # Additional checks for small images and company logos
                if not ('50x50' in src or '100x100' in src or '150x150' in src):
                    # Skip if URL contains typical logo paths
                    if not any(x in clean_src.lower() for x in ['/logo/', '/brand/', '/agent/']):
                        details['images'].append(clean_src)
        
        details['image_count'] = len(details['images'])
        
        # Set main image - prioritize explicit main_image, then first non-logo image
        if details['images']:
            main_image = next((img for img in details['images'] 
                             if not any(logo_word in img.lower() for logo_word in ['logo', 'agent'])), 
                             details['images'][0])
        
        details['main_image'] = main_image

        # Add site name
        details['site_name'] = self.site_name

        return details
