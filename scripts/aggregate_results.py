#!/usr/bin/env python3
"""
aggregate_results.py - Aggregate benchmark results from multiple adapters
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def load_result_file(filepath: Path) -> Dict:
    """Load a single result JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def aggregate_results(input_dir: Path, output_path: Path):
    """Aggregate all result files into a summary."""
    results = []
    
    # Find all result JSON files
    for adapter_dir in input_dir.iterdir():
        if not adapter_dir.is_dir():
            continue
        
        for result_file in adapter_dir.glob('*_results.json'):
            try:
                result = load_result_file(result_file)
                results.append({
                    'adapter': result.get('adapter_name', result_file.stem.replace('_results', '')),
                    'accuracy': result.get('accuracy', 0),
                    'average_latency_ms': result.get('average_latency_ms', 0),
                    'recall': result.get('recall', 0),
                    'f1_score': result.get('f1_score', 0),
                    'error_count': result.get('error_count', 0),
                    'timestamp': result.get('timestamp', datetime.now().isoformat())
                })
            except Exception as e:
                print(f"Error loading {result_file}: {e}")
    
    # Create summary
    summary = {
        'generated_at': datetime.now().isoformat(),
        'total_adapters': len(results),
        'results': sorted(results, key=lambda x: x['accuracy'], reverse=True)
    }
    
    # Save summary
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Aggregated {len(results)} results to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Aggregate benchmark results')
    parser.add_argument('--input', '-i', required=True, help='Input directory with raw results')
    parser.add_argument('--output', '-o', required=True, help='Output path for summary')
    
    args = parser.parse_args()
    
    aggregate_results(Path(args.input), Path(args.output))


if __name__ == '__main__':
    main()
