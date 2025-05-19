#!/bin/bash

# Build and tag scraper image
echo "Building scraper image..."
docker build -t ghcr.io/enespl/scrapper-job .

# Build and tag web service image
echo "Building web service image..."
docker build -t ghcr.io/enespl/scrapper-web -f web/Dockerfile .

# Push both images
echo "Pushing scraper image..."
docker push ghcr.io/enespl/scrapper-job

echo "Pushing web service image..."
docker push ghcr.io/enespl/scrapper-web

echo "All images built and pushed."
