#!/bin/bash
# setup_cortex.sh - Setup script for SWAL Cortex memory system

set -e

echo "Setting up SWAL Cortex memory system..."

# Check if Cortex is already running (LOCAL MODE - no Docker needed)
if curl -s --max-time 5 http://localhost:8003/health > /dev/null 2>&1; then
    echo "Cortex is already running at http://localhost:8003 (LOCAL MODE)"
    echo "Using existing SWAL Cortex installation"
    exit 0
fi

echo "Cortex not running at localhost:8003"
echo "For local benchmarks, ensure Cortex is running first"
echo "For CI, this step will be skipped"

# For self-hosted runners with Docker
if command -v docker &> /dev/null && [ -n "$CI" ]; then
    echo "Docker found and CI environment, attempting Docker setup..."
    
    # Check if cortex network exists
    docker network create cortex-network 2>/dev/null || true
    
    # Start SurrealDB
    docker run -d \
        --name surrealdb \
        --network cortex-network \
        -p 8000:8000 \
        surrealdb/surrealdb:latest \
        start --protocol ws --bind 0.0.0.0:8000
        
    # Build and run cortex from local source
    if [ -d "/home/runner/work/locomo-benchmark/locomo-benchmark" ]; then
        CORTEX_DIR="/home/runner/work/locomo-benchmark/locomo-benchmark/../cortex"
        if [ -d "$CORTEX_DIR" ]; then
            echo "Building Cortex from source..."
            cd "$CORTEX_DIR"
            docker build -t iberi22/cortex:latest .
            docker run -d \
                --name cortex \
                --network cortex-network \
                -p 8003:8003 \
                -e CORTEX_SURREAL_URL=ws://surrealdb:8000 \
                -e CORTEX_TOKEN=dev-token \
                iberi22/cortex:latest
            cd -
        fi
    fi
    echo "Cortex containers started via Docker"
else
    echo "Skipping Docker setup (not available or not CI)"
fi

# Wait for services to be ready
echo "Waiting for Cortex to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s --max-time 5 http://localhost:8003/health > /dev/null 2>&1; then
        echo "Cortex is ready!"
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo "WARNING: Cortex health check failed after $max_attempts attempts"
exit 1
