#!/bin/bash

# Start yacron
yacron &

# Start web service
python web_service.py >> /var/log/web_service.log 2>&1

# Keep container running (optional, if web_service.py keeps the container alive)
tail -f /var/log/web_service.log
