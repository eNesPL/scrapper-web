#!/bin/bash

# Start web service
python web_service.py >> /var/log/web_service.log 2>&1
