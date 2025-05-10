import requests
from bs4 import BeautifulSoup
import re
from .base_scraper import BaseScraper

class AdresowoScraper(BaseScraper):
    """
    Scraper for Adresowo.pl real estate listings.
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.hardcoded_listings_url, headers=headers, timeout=15)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.text
        except requests.RequestException as e:
            print(f"[{self.site_name}] Error fetching listings page {self.hardcoded_listings_url}: {e}")
            return None

    def parse_listings(self, html_content):
        """
        Parses the listings page HTML to extract individual listing URLs or summary data.
        :param html_content: str, HTML content of the listings page.
        :return: List of dictionaries, each with at least a 'url', 'title', and 'price'.
        """
        if not html_content:
            print(f"[{self.site_name}] No HTML content to parse for listings.")
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Listings are typically in <section class="row offerIGrid ..."> elements
        # or similar sections having 'data-item-id'
        listing_sections = soup.find_all('section', class_=lambda x: x and 'offerIGrid' in x.split())

        print(f"[{self.site_name}] Found {len(listing_sections)} potential listing sections on the page.")

        for section in listing_sections:
            url_suffix = section.get('data-href')
            if not url_suffix:
                # Fallback: try to find an <a> tag with the link
                link_tag = section.find('a', href=re.compile(r'^/o/'))
                if link_tag:
                    url_suffix = link_tag.get('href')

            if not url_suffix:
                # print(f"[{self.site_name}] Skipping a section, no URL suffix found.")
                continue
            
            full_url = self.base_url + url_suffix

            title = 'N/A'
            title_tag_h2 = section.select_one('div.title-container a.title h2, div.title-container h2.title a, h2.offer-title a') # Common patterns for title
            if title_tag_h2:
                title = title_tag_h2.get_text(strip=True)
            else: # Fallback to a.title attribute or text
                title_link_tag = section.select_one('a.title, a.isFavouriteEnabled') # These often have title attributes or text
                if title_link_tag:
                    title_attr = title_link_tag.get('title', '').strip()
                    if title_attr:
                        title = title_attr
                    else: # If title attribute is empty, try its direct text
                        title = title_link_tag.get_text(strip=True)
                        if not title: # If text is also empty, check h2 inside this link
                           h2_inside = title_link_tag.find('h2')
                           if h2_inside: title = h2_inside.get_text(strip=True)


            price = 'N/A'
            price_tag = section.select_one('div.price-container p.price, p.offer-price') # Common patterns for price
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                price = price_text.replace('\xa0', ' ') # Replace non-breaking space
            
            if title == 'N/A' and price == 'N/A' and full_url == self.base_url + url_suffix : # Likely not a valid listing item if all are default
                 # print(f"[{self.site_name}] Skipping section, seems invalid (URL: {full_url}, Title: {title}, Price: {price})")
                 pass # Allow it for now, maybe details page has info

            listing_data = {
                'url': full_url,
                'title': title,
                'price': price
            }
            listings.append(listing_data)
            
        print(f"[{self.site_name}] Parsed {len(listings)} listings from page.")
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
        title_tag = soup.select_one('header.offerHeader h1, h1[itemprop="name"]')
        if title_tag:
            details['title'] = title_tag.get_text(strip=True)
        else: # Fallback to OpenGraph title
            og_title = soup.find('meta', property='og:title')
            details['title'] = og_title['content'].strip() if og_title and og_title.get('content') else 'N/A'
        
        # Price
        price_tag = soup.select_one('aside[role="complementary"] p.price strong, div.priceBox p.price strong')
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            details['price'] = price_text.replace('\xa0', ' ') # Normalize non-breaking space
        else: # Fallback if the primary selector fails
            price_tag_fallback = soup.select_one('p.price strong') # A more generic one
            if price_tag_fallback:
                 price_text = price_tag_fallback.get_text(strip=True)
                 details['price'] = price_text.replace('\xa0', ' ')
            else:
                details['price'] = 'N/A'

        # Description
        description_tag = soup.select_one('div.description[itemprop="description"]')
        if description_tag:
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
        photo_count_element = soup.select_one('div.photoCount, span.photo-count-format, span.photos-count') # Common patterns for a counter
        if photo_count_element:
            count_text = photo_count_element.get_text(strip=True)
            # Try to parse "X / Y" or just "Y"
            match_xy = re.search(r'(\d+)\s*/\s*(\d+)', count_text) # "X / Y"
            match_y = re.search(r'(\d+)', count_text) # Just "Y"
            if match_xy:
                image_count = int(match_xy.group(2)) # Total count
            elif match_y:
                image_count = int(match_y.group(1)) # The number found
        
        if image_count == 0:
            # Fallback: Count <li> items in the photo list (thumbnails)
            gallery_list_items = soup.select('div#photoList ul li, ul.photo-thumbs li')
            if gallery_list_items:
                image_count = len(gallery_list_items)
            else:
                # Fallback: count <img> tags in a general gallery section
                gallery_images = soup.select('div.gallery img, div.photoList img, section.gallery img, div[itemprop="image"] img')
                if gallery_images:
                    image_count = len(gallery_images)
        
        details['image_count'] = image_count
        
        # The BaseScraper will handle setting defaults for missing fields.
        # This scraper just returns what it found.
        print(f"[{self.site_name}] Parsed details: Title='{details.get('title', 'N/A')[:30]}...', Price='{details.get('price', 'N/A')}', ImgCount={details.get('image_count', 0)}")
        return details
