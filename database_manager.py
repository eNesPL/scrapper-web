import sqlite3
import datetime
import json # For storing list of features if needed, or other complex types

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn

    def init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            site_name TEXT NOT NULL,
            title TEXT,
            price TEXT,
            description TEXT,
            image_count INTEGER,
            first_image_url TEXT,
            raw_data TEXT, -- Store all scraped data as JSON
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Add indexes for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_url ON listings (url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_site_name ON listings (site_name)")
        conn.commit()
        conn.close()
        print(f"Database '{self.db_name}' initialized/checked.")

    def get_listing_by_url(self, url):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE url = ?", (url,))
        listing = cursor.fetchone()
        conn.close()
        return listing

    def add_listing(self, data):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Ensure all expected keys are present, defaulting to None if not
        # This also helps define the structure of 'data' expected by this method
        keys = ['url', 'site_name', 'title', 'price', 'description', 'image_count', 'first_image_url'] # Added first_image_url
        listing_data_tuple = (
            data.get('url'),
            data.get('site_name'),
            data.get('title'),
            data.get('price'),
            data.get('description'),
            data.get('image_count'),
            data.get('first_image_url'), # Added first_image_url
            json.dumps(data), # Store all data as JSON
            datetime.datetime.now(), # last_updated
            datetime.datetime.now()  # last_checked
        )

        try:
            cursor.execute("""
            INSERT INTO listings (url, site_name, title, price, description, image_count, first_image_url, raw_data, last_updated, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, listing_data_tuple)
            conn.commit()
            print(f"Added new listing: {data.get('url')}")
        except sqlite3.IntegrityError:
            print(f"Error: Listing with URL {data.get('url')} already exists. Use update_listing instead.")
        except Exception as e:
            print(f"Error adding listing {data.get('url')}: {e}")
        finally:
            conn.close()

    def update_listing(self, url, update_data):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Prepare the SET part of the SQL query dynamically
        set_clauses = []
        values = []
        
        # Fields that have dedicated columns and should be updated from update_data
        direct_column_fields = ['title', 'price', 'description', 'image_count', 'first_image_url', 'site_name']
        
        for field in direct_column_fields:
            if field in update_data: # Check if the scraper provided this field
                set_clauses.append(f"{field} = ?")
                values.append(update_data[field])
        
        # Always update raw_data with the full update_data dictionary
        # This ensures all scraped fields, like area_m2, are stored.
        set_clauses.append("raw_data = ?")
        values.append(json.dumps(update_data))

        # If only raw_data was set (e.g. no direct_column_fields were in update_data, which is unlikely but possible),
        # set_clauses would still not be empty.
        # The original check for empty set_clauses might be too strict if we always add raw_data.
        # However, if update_data itself was empty, json.dumps({}) is "{}", which is valid.

        # Always update last_updated and last_checked timestamps
        set_clauses.append("last_updated = ?")
        values.append(datetime.datetime.now())
        set_clauses.append("last_checked = ?")
        values.append(datetime.datetime.now())
        
        values.append(url) # For the WHERE clause

        sql = f"UPDATE listings SET {', '.join(set_clauses)} WHERE url = ?"
        
        try:
            cursor.execute(sql, tuple(values))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"Updated listing: {url}")
            else:
                print(f"No listing found with URL {url} to update, or data was identical.")
        except Exception as e:
            print(f"Error updating listing {url}: {e}")
        finally:
            conn.close()

    def update_last_checked(self, url):
        """Updates only the last_checked timestamp for a listing."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE listings SET last_checked = ? WHERE url = ?", 
                           (datetime.datetime.now(), url))
            conn.commit()
        except Exception as e:
            print(f"Error updating last_checked for {url}: {e}")
        finally:
            conn.close()

