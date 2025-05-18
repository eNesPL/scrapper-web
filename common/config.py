# Configuration for the Real Estate Scraper

# SQLite Database
DATABASE_NAME = "listings.db"

# Discord Notifications
# IMPORTANT: Replace with your actual Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1166999199112511529/1mCawlZTMlUOazD8vt9K_0mI5iIrHFDm1VfMLFE_9V2m05sF7iixcOLpb1kgohkT5cCA" 

# Set to None or empty string to disable Discord notifications
# DISCORD_WEBHOOK_URL = None

# Fields to track for changes in existing listings
TRACKED_FIELDS_FOR_NOTIFICATION = ['price', 'description', 'image_count']
