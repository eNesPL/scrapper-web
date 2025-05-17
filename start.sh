#!/bin/bash

# Run the scraper every hour in the background using nohup
nohup python main.py >> /var/log/scraper.log 2>&1 &

# Wait a few seconds to ensure the scraper starts
sleep 5

# Start web service
python web_service.py >> /var/log/web_service.log 2>&1

# Keep container running (optional, if web_service.py keeps the container alive)
tail -f /var/log/web_service.log
