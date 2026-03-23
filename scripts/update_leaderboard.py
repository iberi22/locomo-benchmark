#!/usr/bin/env python3
"""
update_leaderboard.py - Update the benchmark leaderboard
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def update_leaderboard(results_path: Path, output_path: Path = None):
    """Update the leaderboard with latest results."""
    
    if output_path is None:
        output_path = Path('results/leaderboard.md')
    
    with open(results_path, 'r') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    
    leaderboard = f"""# LoCoMo Memory Benchmark Leaderboard

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*

## Overall Rankings

| Rank | System | Accuracy | Latency | Recall | F1 |
|------|--------|----------|---------|--------|-----|
"""
    
    for i, r in enumerate(results, 1):
        tier = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        leaderboard += f"| {tier} {i} | {r['adapter']} | {r['accuracy']*100:.1f}% | {r['average_latency_ms']:.1f}ms | {r['recall']*100:.1f}% | {r['f1_score']:.3f} |\n"
    
    leaderboard += """
## How to Improve

1. **Optimize retrieval latency** - Consider caching frequent queries
2. **Improve recall** - Add semantic embeddings for better matching
3. **Enhance accuracy** - Implement better context understanding

---
*Participate: Submit your memory system adapter to the benchmark!*
"""
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(leaderboard)
    
    print(f"Leaderboard updated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Update benchmark leaderboard')
    parser.add_argument('--results', '-r', required=True, help='Path to summary JSON')
    parser.add_argument('--output', '-o', default='results/leaderboard.md', help='Output path')
    
    args = parser.parse_args()
    
    update_leaderboard(Path(args.results), Path(args.output))


if __name__ == '__main__':
    main()
