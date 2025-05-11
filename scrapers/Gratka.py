import requests
from bs4 import BeautifulSoup

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
        # TODO: Implement actual web request to the listing_url
        pass

    def parse_listing_details(self, html_content):
        """
        Parses the listing detail page HTML to extract detailed property information.
        :param html_content: str, HTML content of the listing detail page.
        :return: Dictionary with detailed property info.
        """
        print(f"[{self.site_name}] Parsing listing details page content.")
        if not html_content:
            return {}
        # TODO: Implement HTML parsing logic for Gratka.pl listing detail page
        # details = {}
        # details.setdefault('title', 'N/A')
        # details.setdefault('price', 'N/A')
        # details.setdefault('description', 'N/A')
        # details.setdefault('image_count', 0)
        # return details
        return {}
