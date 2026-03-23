#!/bin/bash
# setup_engram.sh - Setup script for Gentleman-Programming/engram

set -e

echo "Setting up Engram memory system..."

# Check if Engram is already running
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "Engram is already running at http://localhost:8080"
    exit 0
fi

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Docker found, starting Engram via Docker..."
    
    # Engram setup - check their official docs for exact image
    docker run -d \
        --name engram \
        -p 8080:8080 \
        -e NODE_ENV=production \
        ghcr.io/gentleman-programming/engram:latest
        
    echo "Engram container started"
else
    echo "Docker not found, please ensure Engram is running at http://localhost:8080"
fi

# Wait for services to be ready
echo "Waiting for Engram to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "Engram is ready!"
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo "WARNING: Engram health check failed after $max_attempts attempts"
echo "Please ensure Engram is running properly"
exit 1
