from flask import Flask, render_template, jsonify
from database_manager import DatabaseManager
from notification_manager import NotificationManager
import config

app = Flask(__name__)
notification_manager = NotificationManager(config.DISCORD_WEBHOOK_URL)

import json

def get_listings_from_db():
    """Fetch all listings from the database"""
    from flask import request
    db_manager = DatabaseManager(config.DATABASE_NAME)
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    
    sort = request.args.get('sort', 'date_desc')
    order_by = {
        'price_asc': 'CAST(price AS REAL) ASC',
        'price_desc': 'CAST(price AS REAL) DESC',
        'date_asc': 'first_seen ASC',
        'date_desc': 'first_seen DESC'
    }.get(sort, 'first_seen DESC')
    
    # Pobierz wszystkie dane i posortuj w Pythonie dla bardziej złożonych przypadków
    cursor.execute("SELECT * FROM listings")
    rows = cursor.fetchall()
    listings = []
    for row in rows:
        listing = dict(row)
        # Parse raw_data to extract additional fields
        try:
            raw_data_str = listing.get('raw_data', '{}')
            # Standardize and convert price to float for sorting
            if listing.get('price'):
                try:
                    price_str = str(listing['price'])
                    # Clean price string - remove zł, spaces, commas
                    price_clean = price_str.replace('zł', '').replace(' ', '').replace(',', '.').strip()
                    listing['price_float'] = float(price_clean) if price_clean.replace('.', '').isdigit() else None
                except (ValueError, TypeError):
                    listing['price_float'] = None
            print(f"Processing listing URL: {listing.get('url')}, Raw data string from DB: {raw_data_str[:200]}...") # Log raw_data
            raw_data = json.loads(raw_data_str)
            
            listing['area_m2'] = raw_data.get('area_m2', 'N/A')
            listing['price'] = raw_data.get('price', listing.get('price', 'N/A')) # Prefer raw_data, fallback to column
            description_from_raw = raw_data.get('description') # Get description from raw_data first
            
            # Use description from raw_data if available, otherwise fallback to column, then 'N/A'
            listing['description'] = description_from_raw if description_from_raw is not None else listing.get('description', 'N/A')
            listing['main_image'] = raw_data.get('main_image', None)  # Add main image from raw_data

            # Ensure that empty or whitespace-only descriptions are treated as 'N/A'
            if not listing['description'] or listing['description'].isspace():
                listing['description'] = 'N/A'
                
            print(f"Extracted area_m2: {listing['area_m2']} for URL: {listing.get('url')}") # Log extracted area
        except (json.JSONDecodeError, TypeError) as e: # Added TypeError for listing.get('raw_data') if it's not a string
            print(f"Error decoding raw_data for listing {listing.get('url')}: {e}. Raw data: {listing.get('raw_data', '')[:200]}")
            listing['area_m2'] = 'N/A'
            # Fallback logic for price and description in case of error
            listing['price'] = listing.get('price', 'N/A') # Fallback to column price if raw_data fails
            listing['description'] = listing.get('description', 'N/A') # Fallback to column description
        listings.append(listing)
    
    # Sortowanie po cenach
    if sort == 'price_asc':
        listings.sort(key=lambda x: x.get('price_float', float('inf')))
    elif sort == 'price_desc':
        listings.sort(key=lambda x: x.get('price_float', float('-inf')), reverse=True)
    elif sort == 'date_asc':
        listings.sort(key=lambda x: x.get('first_seen', ''))
    else:  # date_desc
        listings.sort(key=lambda x: x.get('first_seen', ''), reverse=True)

    conn.close()
    return listings

@app.route('/')
def index():
    """Display a HTML page with all listings"""
    listings = get_listings_from_db()
    return render_template('listings.html', 
                         listings=listings,
                         notification_manager=notification_manager)

@app.route('/api/listings')
def api_listings():
    """JSON API endpoint for listings"""
    listings = get_listings_from_db()
    return jsonify(listings)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
