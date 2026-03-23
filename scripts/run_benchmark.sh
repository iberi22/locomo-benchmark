#!/bin/bash
# run_benchmark.sh - Local benchmark runner

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "================================================"
echo "LoCoMo Memory Benchmark - Local Runner"
echo "================================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not found"
    exit 1
fi

# Create results directory
mkdir -p results

# Parse arguments
ADAPTER="${1:-all}"
OUTPUT_DIR="${2:-results}"

echo "Configuration:"
echo "  Adapter: $ADAPTER"
echo "  Output: $OUTPUT_DIR"
echo ""

# Check if data file exists, if not download it
if [ ! -f "data/locomo10.json" ]; then
    echo "Downloading LoCoMo dataset..."
    mkdir -p data
    
    # Try to download from GitHub
    if command -v curl &> /dev/null; then
        curl -fsSL \
            -o data/locomo10.json \
            "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json" \
            || curl -fsSL \
                -o data/locomo10.json \
                "https://raw.githubusercontent.com/iberi22/locomo/main/data/locomo10.json" \
                || echo "WARNING: Could not download dataset"
    elif command -v wget &> /dev/null; then
        wget -O data/locomo10.json \
            "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json" \
            || echo "WARNING: Could not download dataset"
    fi
fi

# Check if dataset exists
if [ ! -f "data/locomo10.json" ]; then
    echo "ERROR: Dataset not found at data/locomo10.json"
    echo "Please download from https://github.com/snap-research/locomo"
    exit 1
fi

# Run setup scripts based on adapter
if [ "$ADAPTER" == "all" ] || [ "$ADAPTER" == "cortex" ]; then
    echo "Setting up Cortex..."
    bash scripts/setup_cortex.sh || echo "Cortex setup warning (may already be running)"
fi

if [ "$ADAPTER" == "all" ] || [ "$ADAPTER" == "engram" ] || [ "$ADAPTER" == "openclaw_engram" ]; then
    echo "Setting up Engram..."
    bash scripts/setup_engram.sh || echo "Engram setup warning (may already be running)"
fi

# Wait for services to stabilize
echo "Waiting for services to stabilize..."
sleep 5

# Run the benchmark
echo ""
echo "Running benchmark..."
echo ""

python3 src/benchmark_runner.py \
    --adapter $ADAPTER \
    --output "$OUTPUT_DIR"

echo ""
echo "================================================"
echo "Benchmark complete! Results are in: $OUTPUT_DIR"
echo "================================================"
