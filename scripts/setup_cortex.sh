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

echo "Cortex not accessible at localhost:8003"

# If we're in CI, we can't run Cortex tests without access to the local server
if [ "$CI" = "true" ]; then
    echo "CI environment detected - cannot access localhost:8003"
    echo "Skipping Cortex benchmark in CI (requires self-hosted runner with Cortex access)"
    echo "To run Cortex benchmarks, use a self-hosted runner where Cortex is running"
    # In CI, we skip the benchmark entirely by exiting 0 but letting the benchmark runner detect no service
    exit 0
fi

echo "Not in CI - attempting Docker setup..."

# For self-hosted runners with Docker
if command -v docker &> /dev/null; then
    echo "Docker found, attempting Docker setup..."
    
    # Check if cortex network exists
    docker network create cortex-network 2>/dev/null || true
    
    # Start SurrealDB
    docker run -d \
        --name surrealdb \
        --network cortex-network \
        -p 8000:8000 \
        surrealdb/surrealdb:latest \
        start --protocol ws --bind 0.0.0.0:8000
        
    # Build and run cortex from local source if available
    CORTEX_SOURCE_DIR=""
    if [ -d "$(dirname "$0")/../../cortex" ]; then
        CORTEX_SOURCE_DIR="$(dirname "$0")/../../cortex"
    elif [ -d "/home/runner/work/locomo-benchmark/locomo-benchmark/../cortex" ]; then
        CORTEX_SOURCE_DIR="/home/runner/work/locomo-benchmark/locomo-benchmark/../cortex"
    fi
    
    if [ -n "$CORTEX_SOURCE_DIR" ] && [ -f "$CORTEX_SOURCE_DIR/Dockerfile" ]; then
        echo "Building Cortex from source at $CORTEX_SOURCE_DIR..."
        cd "$CORTEX_SOURCE_DIR"
        docker build -t iberi22/cortex:benchmark .
        docker run -d \
            --name cortex \
            --network cortex-network \
            -p 8003:8003 \
            -e CORTEX_SURREAL_URL=ws://surrealdb:8000 \
            -e CORTEX_TOKEN=dev-token \
            iberi22/cortex:benchmark
        cd -
        echo "Cortex container started via Docker"
    else
        echo "Cortex source not found at $CORTEX_SOURCE_DIR"
        echo "Skipping Docker setup"
    fi
else
    echo "Docker not available, skipping setup"
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
echo "Cortex benchmark will be skipped"
exit 0
