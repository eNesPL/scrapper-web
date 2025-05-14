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
                        # Removed print from here, will be listed later
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

    available_scrapers_dict = discover_scrapers()

    # Remove specific scrapers we want to disable
    scrapers_to_disable = ['sprzedajemyScraper', 'SzybkoScraper']
    for scraper_name in scrapers_to_disable:
        if scraper_name in available_scrapers_dict:
            del available_scrapers_dict[scraper_name]
            print(f"Disabled scraper: {scraper_name}")

    if not available_scrapers_dict:
        print("No scrapers found. Make sure scraper modules are in the 'scrapers' directory,")
        print("inherit from BaseScraper, and that 'scrapers/__init__.py' exists.")
        return

    print("\nDostępne scrapers:")
    print("0. Uruchom WSZYSTKIE scrapers")
    scraper_display_list = []
    # Sort scrapers by class name for consistent ordering
    sorted_scraper_items = sorted(available_scrapers_dict.items())

    for i, (class_name, scraper_class) in enumerate(sorted_scraper_items):
        try:
            temp_instance = scraper_class(db_manager=None, notification_manager=None)
            site_display_name = temp_instance.site_name
        except TypeError as e: 
            site_display_name = f"{class_name} (Błąd: nieprawidłowa sygnatura __init__? {e})"
        except Exception as e:
            site_display_name = f"{class_name} (Błąd podczas inicjalizacji: {e})"
        
        scraper_display_list.append({'id': i + 1, 'name': site_display_name, 'class_name': class_name, 'class': scraper_class})
        print(f"{i + 1}. {site_display_name} (Klasa: {class_name})")
    
    # Uruchom wszystkie scrapers
    if scraper_display_list:
        if selected_scraper_info == "ALL":
            print("\nRunning ALL scrapers...")
            search_criteria = {
                'location': 'Gliwice',
                'property_type': 'apartment',
                'min_beds': 2,
                'max_price': 300000,
                'min_area': 25
            }
            
            for scraper_info in scraper_display_list:
                try:
                    scraper_instance = scraper_info['class'](db_manager=db_manager, notification_manager=notification_manager)
                    print(f"\nRunning scraper: {scraper_instance.site_name} with criteria: {search_criteria}")
                    scraper_instance.scrape(search_criteria)
                    print(f"Completed scraping for {scraper_instance.site_name}")
                except Exception as e:
                    print(f"Error running {scraper_info['name']}: {e}")
                    continue
        else:
            search_criteria = {
                'location': 'Gliwice',
                'property_type': 'apartment',
                'min_beds': 2,
                'max_price': 300000,
                'min_area': 25
            }
            
            print("\nRunning ALL scrapers...")
            for scraper_info in scraper_display_list:
                try:
                    scraper_instance = scraper_info['class'](db_manager=db_manager, notification_manager=notification_manager)
                    print(f"\nRunning scraper: {scraper_instance.site_name} with criteria: {search_criteria}")
                    scraper_instance.scrape(search_criteria)
                    print(f"Completed scraping for {scraper_instance.site_name}")
                except Exception as e:
                    print(f"Error running {scraper_info['name']}: {e}")
                    continue
        # Optionally, display data from DB or summary stats here
        
    else: # Should not be reached if loop for selection works correctly
        print(f"Could not select a scraper to run.")


if __name__ == "__main__":
    main()
