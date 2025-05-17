#!/bin/bash

# Run the scraper every hour
while true; do
  python main.py >> /var/log/scraper.log 2>&1
  sleep 3600  # Sleep for 3600 seconds (1 hour)
done

# Start web service
python web_service.py &

# Keep container running
tail -f /dev/null
