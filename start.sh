#!/bin/bash

# Run the scraper every hour in the background using nohup
while true; do
  nohup python main.py >> /var/log/scraper.log 2>&1 &
  sleep 3600  # Sleep for 1 hour
done &

# Wait a few seconds to ensure the scraper starts
sleep 5

# Start web service
python web_service.py >> /var/log/web_service.log 2>&1

# Keep container running (optional, if web_service.py keeps the container alive)
tail -f /var/log/web_service.log
