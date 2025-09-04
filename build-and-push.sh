#!/bin/bash

# Build and tag scraper image
echo "Building scraper image..."
docker build -t ghcr.io/enespl/scrapper-job:latest -f scraper/Dockerfile ./scraper

# Build and tag web service image
echo "Building web service image..."
docker build -t ghcr.io/enespl/scrapper-web:latest -f web/Dockerfile ./web

# Push both images
echo "Pushing scraper image..."
docker push ghcr.io/enespl/scrapper-job:latest

echo "Pushing web service image..."
docker push ghcr.io/enespl/scrapper-web:latest

echo "All images built and pushed."

#kubectl rollout restart deployment real-estate-web-deployment -n scrapper
