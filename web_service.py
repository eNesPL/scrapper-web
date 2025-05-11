from flask import Flask, render_template, jsonify
from database_manager import DatabaseManager
import config

app = Flask(__name__)

import json

def get_listings_from_db():
    """Fetch all listings from the database"""
    db_manager = DatabaseManager(config.DATABASE_NAME)
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM listings ORDER BY last_updated DESC")
    rows = cursor.fetchall()
    conn.close()
    
    listings = []
    for row in rows:
        listing = dict(row)
        # Parse raw_data to extract additional fields
        try:
            raw_data_str = listing.get('raw_data', '{}') # Get raw_data string, default to empty JSON string
            print(f"Processing listing URL: {listing.get('url')}, Raw data string from DB: {raw_data_str[:200]}...") # Log raw_data
            raw_data = json.loads(raw_data_str)
            
            listing['area_m2'] = raw_data.get('area_m2', 'N/A')
            listing['price'] = raw_data.get('price', listing.get('price', 'N/A')) # Prefer raw_data, fallback to column
            listing['description'] = raw_data.get('description', listing.get('description', 'N/A')) # Prefer raw_data, fallback to column
            
            print(f"Extracted area_m2: {listing['area_m2']} for URL: {listing.get('url')}") # Log extracted area
        except (json.JSONDecodeError, TypeError) as e: # Added TypeError for listing.get('raw_data') if it's not a string
            print(f"Error decoding raw_data for listing {listing.get('url')}: {e}. Raw data: {listing.get('raw_data', '')[:200]}")
            listing['area_m2'] = 'N/A'
            listing['price'] = listing.get('price', 'N/A') # Fallback to column price if raw_data fails
            listing['description'] = listing.get('description', 'N/A') # Fallback to column description
        listings.append(listing)
    
    return listings

@app.route('/')
def index():
    """Display a HTML page with all listings"""
    listings = get_listings_from_db()
    return render_template('listings.html', listings=listings)

@app.route('/api/listings')
def api_listings():
    """JSON API endpoint for listings"""
    listings = get_listings_from_db()
    return jsonify(listings)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
