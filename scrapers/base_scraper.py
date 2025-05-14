from abc import ABC, abstractmethod
import datetime # For notification timestamps
import json # For storing raw_data in DB
from config import TRACKED_FIELDS_FOR_NOTIFICATION # Import tracked fields

class BaseScraper(ABC):
    """
    Abstract base class for website-specific real estate scrapers.
    Each scraper for a specific website should inherit from this class
    and implement its abstract methods.
    """

    def __init__(self, site_name, db_manager=None, notification_manager=None):
        """
        Initializes the scraper.
        :param site_name: str, human-readable name of the website.
        :param db_manager: Instance of DatabaseManager.
        :param notification_manager: Instance of NotificationManager.
        """
        self.site_name = site_name
        self.db_manager = db_manager
        self.notification_manager = notification_manager
        if db_manager and notification_manager: # Only print if fully initialized for a run
            print(f"Initialized scraper for: {self.site_name} with DB and Notification support.")
        elif site_name: # For discovery phase
             print(f"Discovered scraper for: {self.site_name} (managers not yet fully initialized).")


    @abstractmethod
    def fetch_listings_page(self, search_criteria, page=1):
        """
        Fetches the HTML content of the main listings page.
        :param search_criteria: dict, search parameters
        :param page: int, page number to fetch (default: 1)
        :return: HTML content (str) or None.
        """
        pass

    @abstractmethod
    def parse_listings(self, html_content):
        """
        Parses listings page HTML to extract individual listing URLs or summary data.
        :return: List of dictionaries, each with at least a 'url'.
                 (e.g., [{'url': '...', 'price': '...', 'title': '...'}, ...])
        """
        pass

    @abstractmethod
    def fetch_listing_details_page(self, listing_url):
        """
        Fetches an individual listing's detail page HTML.
        :return: HTML content (str) or None.
        """
        pass

    @abstractmethod
    def parse_listing_details(self, html_content):
        """
        Parses listing detail page HTML.
        :return: Dictionary with detailed property info.
                 Should include 'price', 'description', 'image_count', 'title'.
                 (e.g., {'price': '$500k', 'description': '...', 'image_count': 5, 'title': 'Big House'})
        """
        pass

    def scrape(self, search_criteria):
        """
        Orchestrates the scraping process with pagination support.
        :param search_criteria: dict, search parameters
        """
        if not self.db_manager or not self.notification_manager:
            print(f"[{self.site_name}] Error: DatabaseManager or NotificationManager not provided. Cannot proceed with full scrape.")
            return []

        print(f"[{self.site_name}] Starting scrape with criteria: {search_criteria}")
        
        processed_properties_data = []
        page = 1
        while page <= self.MAX_PAGES:
            print(f"[{self.site_name}] Processing page {page}")
            
            # Pobierz i przetwórz stronę
            listings_page_html = self.fetch_listings_page(search_criteria, page)
            if not listings_page_html:
                print(f"[{self.site_name}] Failed to fetch page {page}")
                break

            listings_summaries, has_next_page = self.parse_listings(listings_page_html)
            
            if not listings_summaries:
                print(f"[{self.site_name}] No listings on page {page}")
                break

            print(f"[{self.site_name}] Found {len(listings_summaries)} listings on page {page}")

            # Przetwarzanie ogłoszeń
            for i, summary in enumerate(listings_summaries):
                listing_url = summary.get('url')
                
                print(f"[{self.site_name}] Processing listing {i+1}/{len(listings_summaries)}: {listing_url or 'Summary without URL'}")

                if not listing_url:
                    print(f"[{self.site_name}] Warning: Listing summary does not contain a 'url'. Skipping.")
                    continue

                details_page_html = self.fetch_listing_details_page(listing_url)
                if not details_page_html:
                    print(f"[{self.site_name}] Failed to fetch details page for {listing_url}. Skipping.")
                    if self.db_manager.get_listing_by_url(listing_url):
                        self.db_manager.update_last_checked(listing_url)
                    continue

                detailed_data = self.parse_listing_details(details_page_html)
                if not detailed_data:
                    print(f"[{self.site_name}] Failed to parse details for {listing_url}. Skipping.")
                    if self.db_manager.get_listing_by_url(listing_url):
                        self.db_manager.update_last_checked(listing_url)
                    continue
                
                current_listing_data = {
                    **summary, 
                    **detailed_data,
                    'url': listing_url,
                    'site_name': self.site_name
                }
                
                # Ensure all tracked fields and other key fields have a default if not provided by scraper
                key_fields_to_default = set(TRACKED_FIELDS_FOR_NOTIFICATION + ['title', 'first_image_url'])
                for field in key_fields_to_default:
                    current_listing_data.setdefault(field, None)
                # Ensure image_count has a numeric default if None
                if current_listing_data.get('image_count') is None:
                    current_listing_data['image_count'] = 0

                existing_listing_row = self.db_manager.get_listing_by_url(listing_url)

                if not existing_listing_row:
                    db_insert_data = {
                        'url': listing_url,
                        'site_name': self.site_name,
                        'title': current_listing_data.get('title'),
                        'price': current_listing_data.get('price'),
                        'description': current_listing_data.get('description'),
                        'image_count': current_listing_data.get('image_count'),
                        'first_image_url': current_listing_data.get('first_image_url'),
                        'raw_data': current_listing_data 
                    }
                    self.db_manager.add_listing(db_insert_data)
                    
                    notif_embed = self.notification_manager.format_new_listing_embed(current_listing_data)
                    self.notification_manager.send_notification(embed=notif_embed)
                    print(f"[{self.site_name}] Added new listing to DB and sent notification: {listing_url}")

                else:
                    update_payload_for_db = {}
                    changes_for_notification = []

                    fields_to_check_for_update = ['title', 'price', 'description', 'image_count', 'first_image_url']

                    for field in fields_to_check_for_update:
                        old_value = existing_listing_row[field]
                        new_value = current_listing_data.get(field)

                        if field == 'image_count':
                            try:
                                old_value = int(old_value) if old_value is not None else None
                                new_value = int(new_value) if new_value is not None else None
                            except (ValueError, TypeError):
                                pass

                        if old_value != new_value:
                            update_payload_for_db[field] = new_value
                            if field in TRACKED_FIELDS_FOR_NOTIFICATION:
                                changes_for_notification.append((field, str(old_value)[:50], str(new_value)[:50]))
                    
                    update_payload_for_db['raw_data'] = current_listing_data
                    
                    dedicated_fields_changed = any(field in update_payload_for_db for field in fields_to_check_for_update)

                    print(f"[{self.site_name}] Updating existing listing (or just timestamps/raw_data) for {listing_url}. Payload keys for dedicated columns: {[k for k in update_payload_for_db if k != 'raw_data']}")
                    self.db_manager.update_listing(listing_url, update_payload_for_db)
                    
                    if changes_for_notification:
                        print(f"[{self.site_name}] Sending notification for changes: {changes_for_notification}")
                        notif_embed = self.notification_manager.format_updated_listing_embed(current_listing_data, changes_for_notification)
                        self.notification_manager.send_notification(embed=notif_embed)
                    elif dedicated_fields_changed:
                        print(f"[{self.site_name}] Updated listing in DB (non-notified dedicated fields changed): {listing_url}")
                    else:
                        print(f"[{self.site_name}] No changes in dedicated fields for {listing_url}. Ensured raw_data and timestamps are current.")

                processed_properties_data.append(current_listing_data)
            
            if not has_next_page:
                break
            page += 1

        print(f"[{self.site_name}] Finished scraping. Processed {len(processed_properties_data)} properties.")
        return processed_properties_data

