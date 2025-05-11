# In a real scraper, you would import libraries like requests and BeautifulSoup:
# import requests
# from bs4 import BeautifulSoup
import requests
from bs4 import BeautifulSoup

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
        # self.base_url = "https://www.domiporta.pl" # Example base URL

    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page from Domiporta.pl.
        :param search_criteria: dict, search parameters (ignored as we use hardcoded URL).
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
        :return: List of dictionaries, each with at least a 'url'.
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
        return listings

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
        area_text = None  # Initialize as None to distinguish from an empty string found
        
        # Try to find by 'features-short__value-quadric' (which is a <p> tag)
        area_quadric_p_tag = soup.find('p', class_='features-short__value-quadric')
        if area_quadric_p_tag:
            extracted_value = area_quadric_p_tag.get_text(strip=True).replace('\xa0', ' ')
            if extracted_value:  # Only use if non-empty
                area_text = extracted_value

        if area_text is None:
            # Try new format if 'features-short__value-quadric' not found or was empty
            area_name_span = soup.find('span', class_='features__item_name', string='Powierzchnia całkowita')
            if area_name_span:
                area_value_span = area_name_span.find_next_sibling('span', class_='features__item_value')
                if area_value_span:
                    extracted_value = area_value_span.get_text(strip=True).replace('\xa0', ' ')
                    if extracted_value:  # Only use if non-empty
                        area_text = extracted_value
        
        if area_text is None:
            # Fallback to old format if other methods fail or returned empty
            area_tag = soup.find('div', class_='paramIconFloorArea')
            if area_tag:
                extracted_value = area_tag.get_text(strip=True).replace('\xa0', ' ')
                if extracted_value:  # Only use if non-empty
                    area_text = extracted_value
        
        details['area_m2'] = area_text if area_text is not None else 'N/A'

        # Description
        description_div = soup.find('div', class_='description')
        if description_div:
            description = ' '.join([p.get_text(strip=True) for p in description_div.find_all('p')])
            details['description'] = description[:500] + '...' if len(description) > 500 else description
        else:
            details['description'] = 'N/A'

        # Image count
        gallery = soup.find('div', class_='gallery')
        if gallery:
            details['image_count'] = len(gallery.find_all('img'))
        else:
            details['image_count'] = 0

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
