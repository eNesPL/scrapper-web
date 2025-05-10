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
            raw_data = json.loads(listing['raw_data'])
            listing['area_m2'] = raw_data.get('area_m2', 'N/A')
            listing['price'] = raw_data.get('price', 'N/A')  # Dodano nowe pole
        except (json.JSONDecodeError, KeyError) as e:
            listing['area_m2'] = 'N/A'
            listing['price'] = 'N/A'  # Domyślna wartość dla ceny
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
