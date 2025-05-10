import importlib
import os
import inspect
import sys
import datetime # Required for NotificationManager embeds

# Import new managers and config
from database_manager import DatabaseManager
from notification_manager import NotificationManager
import config

# This will be dynamically populated by discover_scrapers
# We need to ensure scrapers.base_scraper can be imported first
# by adjusting sys.path before this type hint is resolved by linters in some cases.
# from scrapers.base_scraper import BaseScraper # Moved import to after sys.path adjustment

def discover_scrapers(scrapers_package_dir="scrapers"):
    """
    Dynamically discovers scraper classes in the specified directory.
    Scraper classes must inherit from BaseScraper.
    """
    from scrapers.base_scraper import BaseScraper # Import here after sys.path adjustment

    scraper_classes = {}
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scrapers_abs_path = os.path.join(base_dir, scrapers_package_dir)

    if not os.path.isdir(scrapers_abs_path):
        print(f"Error: Scrapers directory '{scrapers_abs_path}' not found.")
        return scraper_classes

    for filename in os.listdir(scrapers_abs_path):
        if filename.endswith(".py") and filename not in ("__init__.py", "base_scraper.py"):
            module_name_in_package = filename[:-3]
            full_module_path = f"{scrapers_package_dir}.{module_name_in_package}"
            
            try:
                module = importlib.import_module(full_module_path)
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and \
                       issubclass(obj, BaseScraper) and \
                       obj is not BaseScraper:
                        scraper_classes[name] = obj
                        print(f"Discovered scraper: {name} from {full_module_path}")
            except ImportError as e:
                print(f"Error importing module {full_module_path}: {e}")
            except Exception as e:
                print(f"Error processing module {full_module_path}: {e}")
    return scraper_classes

def main():
    print("Real Estate Scraper Framework")
    
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_script_dir
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Initialize DatabaseManager
    db_manager = DatabaseManager(config.DATABASE_NAME)
    db_manager.init_db()

    # Initialize NotificationManager
    notification_manager = NotificationManager(config.DISCORD_WEBHOOK_URL)

    available_scrapers = discover_scrapers()

    if not available_scrapers:
        print("No scrapers found. Make sure scraper modules are in the 'scrapers' directory,")
        print("inherit from BaseScraper, and that 'scrapers/__init__.py' exists.")
        return

    print("\nAvailable scrapers:")
    scraper_display_list = []
    for i, (class_name, scraper_class) in enumerate(available_scrapers.items()):
        try:
            # Instantiate with None for managers during discovery, site_name is primary
            # Scraper __init__ must handle db_manager and notification_manager being None
            temp_instance = scraper_class(db_manager=None, notification_manager=None)
            site_display_name = temp_instance.site_name
        except TypeError as e: 
            site_display_name = f"{class_name} (Error: __init__ signature mismatch? {e})"
        except Exception as e:
            site_display_name = f"{class_name} (Error during init for discovery: {e})"
        
        scraper_display_list.append({'id': i + 1, 'name': site_display_name, 'class_name': class_name, 'class': scraper_class})
        print(f"{i + 1}. {site_display_name} (Class: {class_name})")
    
    scraper_to_run_class_name = "ExampleSiteScraper" # Default to example
    
    selected_scraper_info = next((s for s in scraper_display_list if s['class_name'] == scraper_to_run_class_name), None)

    if not selected_scraper_info and scraper_display_list:
        print(f"\nScraper '{scraper_to_run_class_name}' not found. Running the first available scraper.")
        selected_scraper_info = scraper_display_list[0]
    
    if selected_scraper_info:
        SelectedScraperClass = selected_scraper_info['class']
        print(f"\nAttempting to run scraper: {selected_scraper_info['name']}")
        
        try:
            # Instantiate with actual managers for the run
            scraper_instance = SelectedScraperClass(db_manager=db_manager, notification_manager=notification_manager)
        except Exception as e:
            print(f"Could not instantiate {selected_scraper_info['class_name']} with managers: {e}")
            return

        search_criteria = {
            'location': 'Sample City',
            'property_type': 'apartment',
            'min_beds': 2
        }

        print(f"Running scraper: {scraper_instance.site_name} with criteria: {search_criteria}")
        # The scrape method now handles DB and notifications internally
        scraper_instance.scrape(search_criteria) 

        print(f"\nScraping process completed for {scraper_instance.site_name}.")
        # Optionally, display data from DB or summary stats here
        
    elif not scraper_display_list:
        print("No scrapers available to run.")
    else:
        print(f"Could not select a scraper to run.")


if __name__ == "__main__":
    main()
