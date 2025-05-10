from flask import Flask, render_template, jsonify
from database_manager import DatabaseManager
import config

app = Flask(__name__)

def get_listings_from_db():
    """Fetch all listings from the database"""
    db_manager = DatabaseManager(config.DATABASE_NAME)
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    
    # Get all listings sorted by most recently updated
    cursor.execute("""
    SELECT * FROM listings 
    ORDER BY last_updated DESC
    """)
    
    listings = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    return [dict(row) for row in listings]

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
