# In a real scraper, you would import libraries like requests and BeautifulSoup:
import re
import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
# import datetime # If you need to use datetime objects

class OLXScraper(BaseScraper):
    """
    Scraper for OLX.pl real estate listings.
    """

    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

    MAX_PAGES = 50  # Maksymalna liczba stron do przetworzenia
    
    def __init__(self, db_manager=None, notification_manager=None):
        super().__init__(site_name="OLX.pl",
                         db_manager=db_manager,
                         notification_manager=notification_manager)
        # self.base_url = "https://www.olx.pl" # Example base URL

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the listings page from OLX.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching page {page} with criteria: {search_criteria}")
        base_url = "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/gliwice/"
        params = {
            'search[filter_float_price:to]': 300000,
            'search[filter_float_m:from]': 25,
            'search[filter_enum_rooms][0]': 'two',
            'search[filter_enum_rooms][1]': 'three',
            'page': page
        }
        
        headers = {'User-Agent': self.USER_AGENT}
        
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching listings: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: Tuple of (listings, has_next_page) where listings is a list of dicts with at least 'url',
                 and has_next_page is a boolean indicating if there are more pages.
        """
        # BeautifulSoup jest już importowany na poziomie modułu
        print(f"[{self.site_name}] Parsing listings page content.")
        
        if not html_content:
            return [], False
            
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        stop_processing_page = False # Flaga: czy znaleziono separator na tej stronie

        # Znajdź główny kontener ofert, np. <div data-testid="listing-grid">
        main_content_area = soup.find('div', {'data-testid': 'listing-grid'})

        if not main_content_area:
            print(f"[{self.site_name}] Warning: Could not find 'listing-grid'. Assuming no listings or end of relevant content.")
            return [], False # Brak ofert, brak następnej strony

        # Iteruj po bezpośrednich dzieciach (typu div) głównego kontenera ofert
        for item_container in main_content_area.find_all('div', recursive=False):
            # 1. Sprawdź, czy item_container jest separatorem
            # Separator to <div class="css-wsrviy">...</div>
            if 'css-wsrviy' in item_container.get('class', []):
                print(f"[{self.site_name}] Found 'further distance' separator: {item_container.get('class')}. Stopping parsing for this page.")
                stop_processing_page = True
                break # Koniec przetwarzania tej strony

            # 2. Jeśli nie separator, spróbuj znaleźć w nim kartę oferty
            # Karta oferty to <div data-cy="l-card">
            listing_card = None
            if item_container.get('data-cy') == 'l-card':
                listing_card = item_container
            else:
                # Sprawdź, czy 'l-card' jest dzieckiem 'item_container'
                # (może być zagnieżdżony np. w <div class="css-1sw7q4x">)
                potential_card = item_container.find('div', {'data-cy': 'l-card'})
                if potential_card:
                    listing_card = potential_card
            
            if not listing_card: # To nie separator i nie znaleziono w nim karty
                continue

            # Mamy listing_card, przetwarzamy
            try:
                # Get listing URL
                title_div = listing_card.find('div', {'data-cy': 'ad-card-title'})
                link = title_div.find('a') if title_div else None
                if not link or not link.get('href'):
                    continue
                    
                url = link['href']
                if "otodom.pl" in url:
                    continue  # Ignoruj oferty z Otodom
                if not url.startswith('http'):
                    url = f"https://www.olx.pl{url}"
                
                # Get title
                title = link.get_text().strip() if link else None
                
                # Get price
                price_element = listing_card.find('p', {'data-testid': 'ad-price'})
                price = None
                if price_element:
                    try:
                        # re jest już importowany na poziomie modułu
                        price_text = re.sub(r'[^\d]', '', price_element.get_text())  # Usuń wszystkie niecyfrowe znaki
                        price = float(price_text) if price_text else None
                    except (ValueError, AttributeError):
                        pass
                
                # Get location and date
                location_date = listing_card.find('p', {'data-testid': 'location-date'})
                location = ''
                date = ''
                if location_date:
                    location_parts = location_date.get_text().split(' - ')
                    location = location_parts[0].strip() if len(location_parts) > 0 else ''
                    date = location_parts[1].strip() if len(location_parts) > 1 else ''
                
                # Get size from multiple possible locations
                size = None
                # Try primary location
                size_container = listing_card.find('div', {'color': 'text-global-secondary'})
                if size_container:
                    size_element = size_container.find('span', class_='css-6as4g5')
                    if size_element:
                        try:
                            size_text = size_element.get_text().split('-')[0].replace('m²', '').strip()
                            size = float(size_text.replace(',', '.'))
                        except ValueError:
                            pass
                
                # Try additional location if not found
                if size is None:
                    size_element = listing_card.find('p', string=lambda t: t and 'm²' in t)
                    if size_element:
                        try:
                            size_text = size_element.get_text().replace('m²', '').strip()
                            size = float(size_text.replace(',', '.'))
                        except ValueError:
                            pass

                listing_data = {
                    'url': url,
                    'title': title,
                    'price': price,
                    'location': location,
                    'date_added': date,
                    'size': size
                }
                listings.append(listing_data)
            except Exception as e:
                error_context = str(listing_card)[:200] # Pierwsze 200 znaków karty dla kontekstu błędu
                print(f"Error parsing listing: {e} (context: {error_context}...)")
                continue
                
        # Logika określająca, czy jest następna strona
        if stop_processing_page:
            # Znaleziono separator, więc nie ma sensu iść na następną stronę z tego samego wyszukiwania
            has_next_page = False
        else:
            # Nie znaleziono separatora. Użyj istniejącej logiki: są oferty -> może być następna strona.
            # To jest uproszczenie. Prawdziwa paginacja powinna sprawdzać istnienie przycisku "Next".
            # Jeśli `main_content_area` nie został znaleziony (i zwrócono wcześniej), to ten kod nie zostanie osiągnięty.
            # Jeśli `main_content_area` istniał, ale nie było ofert (np. pusta strona),
            # `listings` będzie puste, `has_next_page` będzie `False`.
            # Sprawdź, czy istnieje klikalny link "Następna strona".
            # Na OLX, aktywny przycisk "dalej" to <a> z data-testid="pagination-forward" i atrybutem href.
            next_page_link = soup.find('a', attrs={'data-testid': 'pagination-forward', 'href': True})
            if next_page_link:
                has_next_page = True
            else:
                has_next_page = False

        return listings, has_next_page

    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML from OLX.pl.
        :param listing_url: str, URL of the individual listing.
        :return: HTML content (str) or None.
        """
        print(f"[{self.site_name}] Fetching details for URL: {listing_url}")
        headers = {'User-Agent': self.USER_AGENT}
        try:
            response = requests.get(listing_url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching details: {e}")
            return None

    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        :param html_content: str, HTML content of the listing detail page.
        :return: Dictionary with detailed property info.
        """
        # BeautifulSoup jest już importowany na poziomie modułu
        print(f"[{self.site_name}] Parsing listing details page content.")
        
        if not html_content:
            return {}
            
        soup = BeautifulSoup(html_content, 'html.parser')
        details = {}
        
        try:
            # Extract title from multiple possible locations
            title = None
            # Try new location first
            title_div = soup.find('div', {'data-cy': 'ad_title', 'data-testid': 'ad_title'})
            if title_div:
                title_h4 = title_div.find('h4')
                if title_h4:
                    title = title_h4.get_text().strip()
            
            # Fallback to old location if not found
            if not title:
                title_h1 = soup.find('h1', {'data-cy': 'ad_title'})
                title = title_h1.get_text().strip() if title_h1 else None
            
            details['title'] = title
            
            # Extract price
            price = soup.find('div', {'data-testid': 'ad-price-container'})
            if price:
                try:
                    price_text = price.find('h3').get_text().replace(' ', '').replace('zł', '').strip()
                    details['price'] = float(price_text) if price_text else None
                except (ValueError, AttributeError):
                    details['price'] = None
            
            # Extract description from multiple locations
            description = ''
            # Primary location
            desc_div = soup.find('div', {'data-cy': 'ad_description'})
            if desc_div:
                description = desc_div.get_text().strip()
            
            # Additional location
            if not description:
                desc_div = soup.find('div', class_='css-1shxysy')
                if desc_div:
                    description = desc_div.get_text().strip()
            
            details['description'] = description
            
            # Extract photos count
            photos = soup.find('div', {'data-testid': 'swiper-list'})
            details['image_count'] = len(photos.find_all('img')) if photos else 0
            
            # Extract first image URL
            first_img = soup.find('img', {'data-testid': 'swiper-image'})
            details['first_image_url'] = first_img.get('src') if first_img else None
            
            # Extract additional parameters from both locations
            params = {}
            
            # Old location (data-cy="ad-parameters")
            params_section = soup.find('div', {'data-cy': 'ad-parameters'})
            if params_section:
                for param in params_section.find_all('li'):
                    key = param.find('span').get_text().strip() if param.find('span') else None
                    value = param.get_text().replace(key, '').strip() if key else None
                    if key and value:
                        params[key] = value
            
            # New location (data-testid="ad-parameters-container")
            params_container = soup.find('div', {'data-testid': 'ad-parameters-container'})
            if params_container:
                for param in params_container.find_all('p', class_='css-1los5bp'):
                    parts = param.get_text().split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        params[key] = value
                    else:
                        # Handle simple key-value pairs without colon
                        params[param.get_text().strip()] = True
            
            # Extract area from parameters if available
            if 'Powierzchnia' in params:
                try:
                    details['area_m2'] = float(params['Powierzchnia'].replace('m²', '').strip())
                except ValueError:
                    pass
            
            # Add all parameters to description
            description = details.get('description', '')
            if params:
                params_text = '\n'.join(f"{k}: {v}" for k, v in params.items())
                details['description'] = f"{description}\n\nDodatkowe parametry:\n{params_text}".strip()
            
            details.update(params)
            
        except Exception as e:
            print(f"Error parsing listing details: {e}")
            
        return details
