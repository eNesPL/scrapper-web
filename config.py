# Configuration for the Real Estate Scraper

# SQLite Database
DATABASE_NAME = "listings.db"

# Discord Notifications
# IMPORTANT: Replace with your actual Discord Webhook URL
DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE" 
# Example: "https://discord.com/api/webhooks/1234567890abcdef/GhijklmnopqrstuvwxyzABCDEF"

# Set to None or empty string to disable Discord notifications
# DISCORD_WEBHOOK_URL = None

# Fields to track for changes in existing listings
# The 'url' field is always used as the primary identifier.
# Other fields listed here will be monitored for changes.
TRACKED_FIELDS_FOR_NOTIFICATION = ['price', 'description', 'image_count']
