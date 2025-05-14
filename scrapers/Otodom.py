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
                'User-Agent': UserAgent().random,
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
            
        # Simple check for next page - we'll assume there are more pages if we found any listings
        # and we're not on the last page (based on MAX_PAGES which is handled in base_scraper)
        has_next_page = len(listings) > 0
        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from Otodom.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        # TODO: Implement actual web request to the listing_url
        # try:
        #     response = requests.get(listing_url, timeout=10)
        #     response.raise_for_status()
        #     return response.text
        # except requests.RequestException as e:
        #     print(f"[{self.site_name}] Error fetching listing details page {listing_url}: {e}")
        #     return None
        pass

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

        # Extract description
        desc_tag = soup.find('div', {'data-cy': 'adPageAdDescription'})
        details['description'] = desc_tag.get_text(strip=True) if desc_tag else 'N/A'

        # Extract parameters from multiple possible sections
        params = {}
        
        # Standard parameters section
        for param in soup.find_all('div', {'class': 'css-1qzszy5'}):
            name = param.find('div', {'class': 'css-1wi2w6s'})
            value = param.find('div', {'class': 'css-1ytkscc'})
            if name and value:
                params[name.get_text(strip=True)] = value.get_text(strip=True)
        
        # Additional parameters section (e.g. in developer listings)
        extra_params = soup.find('div', {'data-testid': 'ad.top-information.table'})
        if extra_params:
            for row in extra_params.find_all('div', {'data-testid': 'table-row'}):
                cells = row.find_all('div')
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if name and value:
                        params[name.replace(':', '')] = value

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

        details['area_m2'] = clean_area(params.get('Powierzchnia') or params.get('Powierzchni', ''))
        details['rooms'] = clean_rooms(params.get('Liczba pokoi') or params.get('Liczba pokoji', ''))
        details['floor'] = params.get('Piętro', 'N/A').split('/')[0].strip()  # Handle format like "parter/2"

        # Extract image count
        images = soup.find_all('img', {'class': 'css-1bmvjcs'})
        details['image_count'] = len(images)

        # Add site name
        details['site_name'] = self.site_name

        return details
