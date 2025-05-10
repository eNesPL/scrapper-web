from abc import ABC, abstractmethod

class BaseScraper(ABC):
    """
    Abstract base class for website-specific real estate scrapers.
    Each scraper for a specific website should inherit from this class
    and implement its abstract methods.
    """

    def __init__(self, site_name):
        """
        Initializes the scraper with the name of the site it targets.
        :param site_name: str, human-readable name of the website.
        """
        self.site_name = site_name
        print(f"Initialized scraper for: {self.site_name}")

    @abstractmethod
    def fetch_listings_page(self, search_criteria):
        """
        Fetches the HTML content of the main listings page based on search criteria.
        
        :param search_criteria: A dictionary of parameters 
                                (e.g., {'location': 'city', 'property_type': 'apartment'})
        :return: HTML content of the listings page (str) or None if an error occurs.
                 In a real implementation, this would use libraries like 'requests'.
        """
        pass

    @abstractmethod
    def parse_listings(self, html_content):
        """
        Parses the HTML content of a listings page to extract individual listing URLs or summary data.
        
        :param html_content: HTML string from fetch_listings_page.
        :return: A list of dictionaries, where each dictionary contains basic info about a listing.
                 Minimally, it should include a 'url' key for the detail page.
                 (e.g., [{'url': '...', 'price': '...', 'address': '...'}, ...])
                 In a real implementation, this would use libraries like 'BeautifulSoup'.
        """
        pass

    @abstractmethod
    def fetch_listing_details_page(self, listing_url):
        """
        Fetches the HTML content of an individual listing detail page.
        
        :param listing_url: The URL of the specific listing.
        :return: HTML content of the detail page (str) or None if an error occurs.
                 In a real implementation, this would use 'requests'.
        """
        pass

    @abstractmethod
    def parse_listing_details(self, html_content):
        """
        Parses the HTML content of a listing detail page to extract detailed information.
        
        :param html_content: HTML string from fetch_listing_details_page.
        :return: A dictionary containing detailed information about the property
                 (e.g., {'bedrooms': 3, 'bathrooms': 2, 'description': '...', 'features': [...]}).
                 In a real implementation, this would use 'BeautifulSoup'.
        """
        pass

    def scrape(self, search_criteria):
        """
        Orchestrates the scraping process for the website.
        1. Fetches the main listings page.
        2. Parses it to get individual listing summaries (including URLs).
        3. For each listing, fetches and parses its details page.
        
        :param search_criteria: A dictionary of search parameters for fetching listings.
        :return: A list of dictionaries, where each dictionary represents a fully scraped property.
        """
        print(f"[{self.site_name}] Starting scrape with criteria: {search_criteria}")
        
        listings_page_html = self.fetch_listings_page(search_criteria)
        if not listings_page_html:
            print(f"[{self.site_name}] Failed to fetch listings page. Aborting scrape for this site.")
            return []

        listings_summaries = self.parse_listings(listings_page_html)
        if not listings_summaries:
            print(f"[{self.site_name}] No listings found or failed to parse listings. Aborting scrape for this site.")
            return []

        print(f"[{self.site_name}] Found {len(listings_summaries)} listings/summaries.")

        all_properties_data = []
        for i, summary in enumerate(listings_summaries):
            listing_url = summary.get('url')
            
            print(f"[{self.site_name}] Processing listing {i+1}/{len(listings_summaries)}: {listing_url or 'Summary without URL'}")

            if not listing_url:
                print(f"[{self.site_name}] Warning: Listing summary does not contain a 'url'. Adding summary data only.")
                all_properties_data.append(summary)
                continue

            details_page_html = self.fetch_listing_details_page(listing_url)
            if not details_page_html:
                print(f"[{self.site_name}] Failed to fetch details page for {listing_url}. Adding summary data only.")
                # Add summary data, potentially marking it as incomplete
                summary_with_error = {**summary, 'detail_fetch_error': True}
                all_properties_data.append(summary_with_error)
                continue

            detailed_data = self.parse_listing_details(details_page_html)
            if not detailed_data: # or if detailed_data is an empty dict and that's an error
                print(f"[{self.site_name}] Failed to parse details for {listing_url}. Adding summary data only.")
                summary_with_error = {**summary, 'detail_parse_error': True}
                all_properties_data.append(summary_with_error)
                continue
            
            # Combine summary data with detailed data.
            # Detailed data keys will overwrite summary keys if they are the same.
            combined_data = {**summary, **detailed_data}
            all_properties_data.append(combined_data)
        
        print(f"[{self.site_name}] Finished scraping. Total properties processed: {len(all_properties_data)}")
        return all_properties_data
