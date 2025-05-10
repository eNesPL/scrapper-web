import importlib
import os
import inspect
import sys

# This will be dynamically populated by discover_scrapers
# We need to ensure scrapers.base_scraper can be imported first
# by adjusting sys.path before this type hint is resolved by linters in some cases.
# from scrapers.base_scraper import BaseScraper # Moved import to after sys.path adjustment

def discover_scrapers(scrapers_package_dir="scrapers"):
    """
    Dynamically discovers scraper classes in the specified directory.
    Scraper classes must inherit from BaseScraper.
    """
    # Import BaseScraper here after sys.path is potentially adjusted
    # This is crucial if main.py is not in the project root or for some execution contexts
    from scrapers.base_scraper import BaseScraper

    scraper_classes = {}
    
    # Construct the absolute path to the scrapers directory
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
    
    # Adjust Python path to include the project root directory (parent of 'scrapers')
    # This allows 'from scrapers.base_scraper import BaseScraper' and
    # 'importlib.import_module(f"scrapers.{module_name}")' to work reliably.
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_script_dir # Assuming main.py is in the project root
    
    # If main.py is in a subfolder and 'scrapers' is a sibling of that subfolder's parent,
    # you might need project_root = os.path.dirname(current_script_dir)
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        # print(f"Added {project_root} to sys.path") # For debugging

    available_scrapers = discover_scrapers()

    if not available_scrapers:
        print("No scrapers found. Make sure scraper modules are in the 'scrapers' directory,")
        print("inherit from BaseScraper, and that 'scrapers/__init__.py' exists.")
        return

    print("\nAvailable scrapers:")
    scraper_display_list = []
    for i, (class_name, scraper_class) in enumerate(available_scrapers.items()):
        try:
            # Temporarily instantiate to get site_name if defined in __init__
            # Assumes scraper __init__ can be called without arguments or has defaults
            temp_instance = scraper_class()
            site_display_name = temp_instance.site_name
        except TypeError: # If __init__ requires arguments
            site_display_name = f"{class_name} (requires arguments for initialization)"
        except Exception as e:
            site_display_name = f"{class_name} (Error during init: {e})"
        
        scraper_display_list.append({'id': i + 1, 'name': site_display_name, 'class_name': class_name, 'class': scraper_class})
        print(f"{i + 1}. {site_display_name} (Class: {class_name})")

    # Example: Run a scraper (e.g., the first one or a specific one)
    # In a real application, you'd let the user choose or configure this.
    
    scraper_to_run_class_name = "ExampleSiteScraper" # Default to example
    
    selected_scraper_info = next((s for s in scraper_display_list if s['class_name'] == scraper_to_run_class_name), None)

    if not selected_scraper_info and scraper_display_list:
        print(f"\nScraper '{scraper_to_run_class_name}' not found. Running the first available scraper.")
        selected_scraper_info = scraper_display_list[0]
    
    if selected_scraper_info:
        SelectedScraperClass = selected_scraper_info['class']
        print(f"\nAttempting to run scraper: {selected_scraper_info['name']}")
        
        try:
            scraper_instance = SelectedScraperClass()
        except Exception as e:
            print(f"Could not instantiate {selected_scraper_info['class_name']}: {e}")
            return

        # Define search criteria (this would typically come from user input or config)
        search_criteria = {
            'location': 'Sample City',
            'property_type': 'apartment',
            'min_beds': 2
        }

        print(f"Running scraper: {scraper_instance.site_name} with criteria: {search_criteria}")
        scraped_data = scraper_instance.scrape(search_criteria)

        if scraped_data:
            print(f"\n--- Scraped Data from {scraper_instance.site_name} ---")
            for i, item in enumerate(scraped_data):
                print(f"--- Property {i+1} ---")
                for key, value in item.items():
                    print(f"  {key}: {value}")
                print("-" * 20)
        else:
            print(f"No data scraped from {scraper_instance.site_name}.")
    elif not scraper_display_list:
        print("No scrapers available to run.")
    else:
        print(f"Could not select a scraper to run.")


if __name__ == "__main__":
    main()
