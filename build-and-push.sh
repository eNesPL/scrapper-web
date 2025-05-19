#!/bin/bash

# Build and tag scraper image
echo "Building scraper image..."
docker build -t your-registry/scraper-image .

# Build and tag web service image
echo "Building web service image..."
docker build -t your-registry/web-image -f web/Dockerfile .

# Push both images
echo "Pushing scraper image..."
docker push your-registry/scraper-image

echo "Pushing web service image..."
docker push your-registry/web-image

echo "All images built and pushed."
