import re
import requests
from bs4 import BeautifulSoup
try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

from .base_scraper import BaseScraper

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

    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page from Gratka.pl.
        :param search_criteria: dict, search parameters (e.g., location, property_type).
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        example_url = f"https://gratka.pl/nieruchomosci/mieszkania/3-pokojowe/gliwice?cena-calkowita:max=300000&location%5Bmap%5D=1&location%5Bmap_bounds%5D=50.3752324,18.7546442:50.2272469,18.5445885&ogloszenie-zawiera%5B0%5D=zdjecie&ogloszenie-zawiera%5B1%5D=cena&powierzchnia-w-m2:min=25&sort=relevance&page={page}"

        print(f"[{self.site_name}] Fetching listings page {page} using URL: {example_url} (Criteria: {search_criteria})")

        try:
            response = requests.get(example_url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page {example_url}: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: Tuple of (listings_summaries, has_next_page)
        """
        print(f"[{self.site_name}] Parsing listings page content.")
        if not html_content:
            return [], False

        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []

        listing_elements = soup.find_all(class_='card')
        if not listing_elements:
            print(f"[{self.site_name}] No elements with class 'card' found. Trying 'article.teaserUnified'.")
            listing_elements = soup.find_all('article', class_='teaserUnified')
        if not listing_elements:
            print(f"[{self.site_name}] No elements with 'article.teaserUnified' found. Trying 'data-testid=listing-item'.")
            listing_elements = soup.find_all(attrs={"data-testid": "listing-item"})

        print(f"[{self.site_name}] Found {len(listing_elements)} potential listing elements using combined methods.")

        for item_element in listing_elements:
            summary = {}
            link_tag = item_element.find('a', class_='teaserUnified__anchor')
            if not link_tag:
                link_tag = item_element.find('a', href=True)

            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                if not url.startswith('http'):
                    summary['url'] = f"{self.base_url}{url if url.startswith('/') else '/' + url}"
                else:
                    summary['url'] = url

                title_tag = link_tag.find('h2', class_='teaserUnified__title')
                if title_tag:
                    summary['title'] = title_tag.get_text(strip=True)
                elif link_tag.get_text(strip=True):
                    summary['title'] = link_tag.get_text(strip=True)
                else:
                    title_span = link_tag.find('span', class_='teaserHeading__mainText')
                    summary['title'] = title_span.get_text(strip=True) if title_span else 'N/A'
            else:
                print(f"[{self.site_name}] Skipping item, no URL found.")
                continue

            price_elements = [
                item_element.find('p', class_='priceInfo__value'),
                item_element.find('span', attrs={"data-testid": "price"}),
                item_element.find('span', class_='teaserUnified__price'),
                item_element.find('span', class_='price'),
                item_element.find('span', class_='value')
            ]
            for price_element in price_elements:
                if price_element:
                    price_text = price_element.get_text(strip=True)
                    if price_text and price_text.lower() != 'zapytaj o cenę':
                        summary['price'] = price_text
                        break
            else:
                summary['price'] = 'N/A'

            listings.append(summary)
            print(f"[{self.site_name}] Parsed summary: {summary}")

        next_button = soup.find('a', class_='pagination__next')
        has_next_page = bool(next_button and 'disabled' not in next_button.get('class', []))
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

        # Inicjalizacja wyników
        details = {
            'title': 'N/A',
            'price': 'N/A',
            'area_m2': 'N/A',
            'description': 'N/A',
            'images': [],
            'image_count': 0,
            'first_image_url': None
        }

        soup = BeautifulSoup(html_content, 'html.parser')
        parameters_section = soup.find('div', class_='parameters__items')  # aby uniknąć późniejszych błędów

        # Parsowanie przez lxml (jeśli dostępne)
        lxml_tree = None
        if lxml_html:
            try:
                lxml_tree = lxml_html.fromstring(html_content)
            except Exception as e:
                print(f"[{self.site_name}] Error parsing HTML with lxml: {e}")

        if lxml_tree is not None:
            try:
                price_el = lxml_tree.xpath('//span[contains(@class,"price")]')
                if price_el:
                    details['price'] = price_el[0].text_content().strip()
                    print(f"[{self.site_name}] Price (XPath): {details['price']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting price with XPath: {e}")

            try:
                area_el = lxml_tree.xpath('//span[contains(text(),"m²")]')
                if area_el:
                    details['area_m2'] = area_el[0].text_content().strip()
                    print(f"[{self.site_name}] Area (XPath): {details['area_m2']}")
            except Exception as e:
                print(f"[{self.site_name}] Error extracting area with XPath: {e}")

        # Tytuł
        h1 = soup.find('h1')
        if h1:
            details['title'] = h1.get_text(strip=True)
        else:
            title_tag = soup.find('title')
            if title_tag:
                details['title'] = title_tag.get_text(strip=True)
        print(f"[{self.site_name}] Title: {details['title']}")

        # Opis
        desc_el = soup.find(attrs={"itemprop": "description"}) or soup.find('div', class_='description__text')
        if desc_el:
            details['description'] = desc_el.get_text(separator="\n", strip=True)

        # Cechy dodatkowe
        features_ul = soup.find('ul', class_='Akny2O')
        if features_ul:
            items = [li.get_text(strip=True) for li in features_ul.find_all('li', attrs={'data-cy': 'tagItem'})]
            if items:
                details['description'] += "\n\nDodatkowe cechy:\n- " + "\n- ".join(items)

        # Galeria zdjęć
        gallery_div = soup.find('div', class_='wM-EsW')
        if gallery_div:
            for btn in gallery_div.find_all('button', class_='_9RlKWz'):
                img = btn.find('img')
                if img and img.get('src'):
                    url = img['src']
                else:
                    # fallback do background-image
                    style = btn.get('style', '')
                    m = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
                    url = m.group(1) if m else None
                if url:
                    if url.startswith('//'):
                        url = f"https:{url}"
                    elif not url.startswith('http'):
                        url = f"{self.base_url}{url}"
                    if url not in details['images']:
                        details['images'].append(url)

        # Liczba i pierwsze zdjęcie
        details['image_count'] = len(details['images'])
        if details['images']:
            details['first_image_url'] = details['images'][0]
        print(f"[{self.site_name}] Images found: {details['image_count']}")

        # Parsowanie powierzchni (fallback BS jeśli XPath nie zadziałał)
        if details['area_m2'] == 'N/A':
            if parameters_section:
                text = parameters_section.get_text(separator=" ", strip=True)
                m = re.search(r'(\d+[\.,]?\d*)\s*(m²|m2|m\s*²)', text, re.IGNORECASE)
                if m:
                    details['area_m2'] = f"{m.group(1).replace(',', '.')} {m.group(2)}"
            if details['area_m2'] == 'N/A':
                m = re.search(r'(\d+[\.,]?\d*)\s*(m²|m2|m\s*²)', soup.get_text(), re.IGNORECASE)
                if m:
                    details['area_m2'] = f"{m.group(1).replace(',', '.')} {m.group(2)}"
        print(f"[{self.site_name}] Area: {details['area_m2']}")

        return details
