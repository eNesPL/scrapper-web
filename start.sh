#!/bin/bash

# Start cron
cron

# Start web service
python web_service.py &

# Keep container running
tail -f /dev/null
