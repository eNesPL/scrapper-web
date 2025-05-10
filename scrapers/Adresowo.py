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
        :return: List of dictionaries, each with at least a 'url', 'title', and 'price'.
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
            # Selectors for price might need adjustment
            price_tag = section.select_one('.offer-summary__value')
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                price = price_text.replace('\xa0', ' ') 
            
            listing_data = {
                'url': full_url,
                'title': title,
                'price': price
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
        
        # Price
        price_text_content = 'N/A'
        # Primary selector based on live page structure for the example URL
        price_container = soup.select_one('aside[role="complementary"] p.price, div.priceBox p.price')
        if price_container:
            strong_tag = price_container.find('strong')
            if strong_tag:
                price_text_content = strong_tag.get_text(strip=True)
            else:
                price_text_content = price_container.get_text(strip=True) # Fallback to p's text if strong is missing
        else:
            # Broader fallback if the main aside/div.priceBox structure isn't found
            price_tag_fallback = soup.select_one('p.price') # Generic p.price
            if price_tag_fallback:
                strong_tag = price_tag_fallback.find('strong')
                if strong_tag:
                    price_text_content = strong_tag.get_text(strip=True)
                else:
                    price_text_content = price_tag_fallback.get_text(strip=True)
        
        details['price'] = price_text_content.replace('\xa0', ' ') if price_text_content != 'N/A' else 'N/A'


        # Description
        description_tag = soup.select_one('div.description[itemprop="description"], section#description div.text') # Added alternative selector
        if description_tag:
            # Remove "Zobacz więcej" or similar buttons/links from description
            for unwanted_tag in description_tag.select('button, a.showMore'):
                unwanted_tag.decompose()
                
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
        # Try to get count from a specific element like "1 / 14" or "14 zdjęć"
        photo_count_element = soup.select_one('div.photoCount, span.photo-count-format, span.photos-count, div.gallery-counter')
        if photo_count_element:
            count_text = photo_count_element.get_text(strip=True)
            # Try to parse "X / Y" or just "Y" or "Y zdjęć"
            match_xy = re.search(r'(\d+)\s*/\s*(\d+)', count_text) # "X / Y"
            match_y_total = re.search(r'/s*(\d+)', count_text) # "/ Y" (total from X/Y)
            match_y_standalone = re.search(r'^(\d+)', count_text) # "Y" or "Y xxx" (count at the beginning)
            
            if match_xy:
                image_count = int(match_xy.group(2)) # Total count from "X / Y"
            elif match_y_total:
                image_count = int(match_y_total.group(1))
            elif match_y_standalone:
                image_count = int(match_y_standalone.group(1)) # The number found
        
        if image_count == 0:
            # Fallback: Count <img> items in the photo gallery thumbnails or main image area
            gallery_thumbnails = soup.select('div#photoList ul li, ul.photo-thumbs li, div.gallery-thumbnails-list li')
            if gallery_thumbnails:
                image_count = len(gallery_thumbnails)
            else:
                # Fallback: count <img> tags in a general gallery section or main image
                gallery_images = soup.select('img')
                if gallery_images:
                    image_count = len(gallery_images)
        
        details['image_count'] = image_count
        
        print(f"[{self.site_name}] Parsed details: Title='{details.get('title', 'N/A')[:30]}...', Price='{details.get('price', 'N/A')}', ImgCount={details.get('image_count', 0)}")
        return details
