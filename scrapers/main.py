import importlib
import os
import inspect
import sys
import argparse

# Import managers and config
from common.database_manager import DatabaseManager  
from common.notification_manager import NotificationManager
from common import config

def discover_scrapers(scrapers_package_dir="scrapers"):
    """
    Dynamically discovers scraper classes in the specified directory.
    Scraper classes must inherit from BaseScraper.
    Returns a dict mapping class names to classes.
    """
    from .scrapers.base_scraper import BaseScraper

    scraper_classes = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scrapers_abs_path = os.path.join(base_dir, scrapers_package_dir)

    if not os.path.isdir(scrapers_abs_path):
        print(f"Error: Scrapers directory '{scrapers_abs_path}' not found.")
        return scraper_classes

    # Iterate through .py files in scrapers directory
    for filename in os.listdir(scrapers_abs_path):
        if not filename.endswith(".py") or filename in ("__init__.py", "base_scraper.py"):
            continue

        module_name = filename[:-3]
        full_module_path = f"{scrapers_package_dir}.{module_name}"
        try:
            module = importlib.import_module(full_module_path)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseScraper) and obj is not BaseScraper:
                    scraper_classes[obj.__name__] = obj
        except Exception as e:
            print(f"Error loading {full_module_path}: {e}")
    return scraper_classes

def main():
    # --- CLI arguments ---
    parser = argparse.ArgumentParser(description="Framework do uruchamiania scraperów")
    parser.add_argument(
        "--only", "-o", nargs="+", metavar="ScraperClass",
        help="Nazwy klas scraperów do uruchomienia (domyślnie wszystkie)"
    )
    args = parser.parse_args()

    # --- Ścieżki i menedżery ---
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    db_manager = DatabaseManager(config.DATABASE_NAME)
    db_manager.init_db()
    notification_manager = NotificationManager(config.DISCORD_WEBHOOK_URL)

    # --- Odkrywanie scraperów ---
    available = discover_scrapers()
    # Wyłącz niechciane
    for name in ("sprzedajemyScraper", "SzybkoScraper"):
        if name in available:
            del available[name]
            print(f"Disabled scraper: {name}")

    if not available:
        print("Brak scraperów do uruchomienia. Sprawdź katalog i dziedziczenie BaseScraper.")
        return

    # --- Wybór scraperów do runu ---
    if args.only:
        # Filtruj tylko wskazane
        to_run = [
            (name, cls) for name, cls in available.items()
            if name in args.only
        ]
        missing = set(args.only) - {name for name, _ in to_run}
        if missing:
            print(f"Uwaga: nie znaleziono scraperów: {', '.join(missing)}")
    else:
        # Domyślnie wszystkie
        to_run = list(available.items())

    # --- Kryteria wyszukiwania ---
    search_criteria = {
        'location': 'Gliwice',
        'property_type': 'apartment',
        'min_beds': 2,
        'max_price': 300000,
        'min_area': 25
    }

    # --- Uruchamianie ---
    for cls_name, cls in sorted(to_run):
        try:
            scraper = cls(db_manager=db_manager, notification_manager=notification_manager)
            print(f"[{cls_name}] Running with criteria: {search_criteria}")
            scraper.scrape(search_criteria)
            print(f"[{cls_name}] Completed successfully\n")
        except Exception as e:
            print(f"[{cls_name}] ERROR: {e}\n")

if __name__ == "__main__":
    main()
