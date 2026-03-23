#!/bin/bash
# setup_cortex.sh - Setup script for SWAL Cortex memory system

set -e

echo "Setting up SWAL Cortex memory system..."

# Check if Cortex is already running
if curl -s http://localhost:8003/health > /dev/null 2>&1; then
    echo "Cortex is already running at http://localhost:8003"
    exit 0
fi

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Docker found, starting Cortex via Docker..."
    
    # Check if cortex network exists
    docker network create cortex-network 2>/dev/null || true
    
    # Start SurrealDB
    docker run -d \
        --name surrealdb \
        --network cortex-network \
        -p 8000:8000 \
        surrealdb/surrealdb:latest \
        start --protocol ws --bind 0.0.0.0:8000
        
    # Start Cortex
    docker run -d \
        --name cortex \
        --network cortex-network \
        -p 8003:8003 \
        -e CORTEX_SURREAL_URL=ws://surrealdb:8000 \
        -e CORTEX_TOKEN=dev-token \
        ghcr.io/southwest-ai-labs/cortex:latest
        
    echo "Cortex containers started"
else
    echo "Docker not found, please ensure Cortex is running at http://localhost:8003"
fi

# Wait for services to be ready
echo "Waiting for Cortex to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8003/health > /dev/null 2>&1; then
        echo "Cortex is ready!"
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo "WARNING: Cortex health check failed after $max_attempts attempts"
echo "Please ensure Cortex is running properly"
exit 1
