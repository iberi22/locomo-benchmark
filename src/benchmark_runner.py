"""
Benchmark Runner - Main orchestrator for LoCoMo memory benchmark

This module orchestrates the benchmarking process for multiple memory systems.
It loads the LoCoMo dataset, runs each adapter through the benchmark, and
produces comprehensive results.
"""

import argparse
import json
import os
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

# Import adapters
from cortex_adapter import CortexAdapter
from engram_adapter import EngramAdapter
from openclaw_engram_adapter import OpenClawEngramAdapter


@dataclass
class BenchmarkResult:
    """Results for a single memory system benchmark."""
    adapter_name: str
    timestamp: str
    total_questions: int
    correct_answers: int
    accuracy: float
    average_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    recall: float
    f1_score: float
    category_results: Dict[str, Dict[str, float]]
    error_count: int
    ingestion_time_ms: float
    raw_answers: List[Dict]


@dataclass
class QAPair:
    """A question-answer pair from the LoCoMo dataset."""
    id: str
    category: str
    context: List[str]
    question: str
    answer: str
    difficulty: str


class BenchmarkRunner:
    """Main benchmark orchestrator."""

    # Default adapter configurations
    DEFAULT_CONFIGS = {
        'cortex': {
            'api_url': os.environ.get('CORTEX_API_URL', 'http://localhost:8003'),
            'token': os.environ.get('CORTEX_TOKEN', 'dev-token'),
            'timeout': 30
        },
        'engram': {
            'api_url': os.environ.get('ENGRAM_API_URL', 'http://localhost:8080'),
            'api_key': os.environ.get('ENGRAM_API_KEY', ''),
            'timeout': 30,
            'vault_id': 'benchmark-vault'
        },
        'openclaw_engram': {
            'api_url': os.environ.get('OPENCLAW_ENGRAM_API_URL', 'http://localhost:8081'),
            'api_key': os.environ.get('OPENCLAW_ENGRAM_API_KEY', ''),
            'timeout': 30,
            'user_id': 'benchmark-user'
        }
    }

    # Random seed for reproducibility
    SEED = 42

    def __init__(self, data_path: str = 'data/locomo10.json'):
        """
        Initialize the benchmark runner.

        Args:
            data_path: Path to the LoCoMo dataset JSON file
        """
        self.data_path = data_path
        self.qa_pairs: List[QAPair] = []
        self.seed(self.SEED)

    def seed(self, seed_value: int):
        """Set random seed for reproducibility."""
        random.seed(seed_value)

    def load_dataset(self) -> List[QAPair]:
        """Load the LoCoMo dataset from JSON file."""
        print(f"Loading dataset from {self.data_path}...")

        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Dataset not found: {self.data_path}")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both list format and dict format with 'data' key
        if isinstance(data, list):
            qa_list = data
        elif isinstance(data, dict) and 'data' in data:
            qa_list = data['data']
        else:
            raise ValueError(f"Unexpected dataset format in {self.data_path}")

        self.qa_pairs = [
            QAPair(
                id=item.get('id', f'qa_{i}'),
                category=item.get('category', 'unknown'),
                context=item.get('context', []),
                question=item.get('question', ''),
                answer=item.get('answer', ''),
                difficulty=item.get('difficulty', 'medium')
            )
            for i, item in enumerate(qa_list)
        ]

        print(f"Loaded {len(self.qa_pairs)} QA pairs")
        return self.qa_pairs

    def evaluate_answer(self, predicted: str, expected: str) -> bool:
        """
        Evaluate if a predicted answer matches the expected answer.

        Uses both exact match and semantic similarity.
        """
        if not predicted or not expected:
            return False

        # Normalize strings
        pred_normalized = predicted.lower().strip()
        exp_normalized = expected.lower().strip()

        # Exact match (case-insensitive)
        if pred_normalized == exp_normalized:
            return True

        # Semantic similarity using SequenceMatcher
        similarity = SequenceMatcher(None, pred_normalized, exp_normalized).ratio()
        if similarity >= 0.85:
            return True

        # Check if expected is contained in predicted
        if exp_normalized in pred_normalized:
            return True

        # Check if predicted is contained in expected
        if pred_normalized in exp_normalized:
            return True

        return False

    def calculate_metrics(
        self,
        results: List[Tuple[str, str, float]],  # (predicted, expected, latency_ms)
        category_results: Dict[str, List[bool]]
    ) -> Dict:
        """Calculate aggregate metrics from benchmark results."""
        total = len(results)
        correct = sum(1 for pred, exp, _ in results if self.evaluate_answer(pred, exp))
        accuracies = [1 if self.evaluate_answer(pred, exp, _) else 0 for pred, exp, _ in results]

        # Latency statistics
        latencies = [lat for _, _, lat in results]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0

        # Recall (simplified - based on accuracy for now)
        recall = correct / total if total > 0 else 0

        # F1 Score
        precision = recall  # Simplified since we're measuring accuracy directly
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Category-specific results
        category_metrics = {}
        for category, category_correct in category_results.items():
            cat_total = len(category_correct)
            cat_correct = sum(category_correct)
            category_metrics[category] = {
                'accuracy': cat_correct / cat_total if cat_total > 0 else 0,
                'count': cat_total
            }

        return {
            'total_questions': total,
            'correct_answers': correct,
            'accuracy': correct / total if total > 0 else 0,
            'average_latency_ms': avg_latency,
            'min_latency_ms': min_latency,
            'max_latency_ms': max_latency,
            'recall': recall,
            'f1_score': f1,
            'category_results': category_metrics
        }

    def run_adapter_benchmark(
        self,
        adapter_name: str,
        adapter_class,
        config: Dict,
        warm_up: int = 3
    ) -> BenchmarkResult:
        """
        Run benchmark for a single memory system adapter.

        Args:
            adapter_name: Name of the adapter for reporting
            adapter_class: The adapter class to instantiate
            config: Configuration dictionary for the adapter
            warm_up: Number of warm-up queries to run

        Returns:
            BenchmarkResult with all metrics
        """
        print(f"\n{'='*60}")
        print(f"Running benchmark for: {adapter_name}")
        print(f"{'='*60}")

        adapter = adapter_class(config)
        timestamp = datetime.now().isoformat()

        # Health check
        print(f"Checking adapter health...")
        if not adapter.health_check():
            print(f"WARNING: Adapter {adapter_name} health check failed")

        # Clear any existing data
        print(f"Clearing existing data...")
        adapter.clear()

        # Prepare context facts for ingestion
        all_contexts = []
        for qa in self.qa_pairs:
            all_contexts.extend(qa.context)
        
        # Deduplicate contexts
        unique_contexts = list(set(all_contexts))
        random.shuffle(unique_contexts)

        # Ingestion phase
        print(f"Ingesting {len(unique_contexts)} facts...")
        ingestion_start = time.time()
        ingestion_success = adapter.ingest(unique_contexts)
        ingestion_time_ms = (time.time() - ingestion_start) * 1000
        print(f"Ingestion {'successful' if ingestion_success else 'failed'} ({ingestion_time_ms:.2f}ms)")

        if not ingestion_success:
            print(f"WARNING: Ingestion failed for {adapter_name}")

        # Warm-up phase
        print(f"Warm-up phase ({warm_up} queries)...")
        for i in range(min(warm_up, len(self.qa_pairs))):
            qa = self.qa_pairs[i]
            adapter.query(qa.question)

        # Query phase
        print(f"Running {len(self.qa_pairs)} queries...")
        results: List[Tuple[str, str, float]] = []
        category_results: Dict[str, List[bool]] = {}
        raw_answers = []
        error_count = 0

        for i, qa in enumerate(self.qa_pairs):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(self.qa_pairs)}")

            predicted, latency_ms = adapter.query(qa.question)
            is_correct = self.evaluate_answer(predicted, qa.answer)

            results.append((predicted, qa.answer, latency_ms))

            if qa.category not in category_results:
                category_results[qa.category] = []
            category_results[qa.category].append(is_correct)

            raw_answers.append({
                'id': qa.id,
                'question': qa.question,
                'expected': qa.answer,
                'predicted': predicted,
                'correct': is_correct,
                'latency_ms': latency_ms,
                'category': qa.category
            })

            if not predicted:
                error_count += 1

        # Calculate metrics
        metrics = self.calculate_metrics(results, category_results)

        # Build result object
        result = BenchmarkResult(
            adapter_name=adapter_name,
            timestamp=timestamp,
            total_questions=metrics['total_questions'],
            correct_answers=metrics['correct_answers'],
            accuracy=metrics['accuracy'],
            average_latency_ms=metrics['average_latency_ms'],
            min_latency_ms=metrics['min_latency_ms'],
            max_latency_ms=metrics['max_latency_ms'],
            recall=metrics['recall'],
            f1_score=metrics['f1_score'],
            category_results=metrics['category_results'],
            error_count=error_count,
            ingestion_time_ms=ingestion_time_ms,
            raw_answers=raw_answers
        )

        # Print summary
        print(f"\n{adapter_name} Results:")
        print(f"  Accuracy: {result.accuracy*100:.1f}%")
        print(f"  Latency: {result.average_latency_ms:.2f}ms (avg)")
        print(f"  Recall: {result.recall*100:.1f}%")
        print(f"  F1 Score: {result.f1_score:.3f}")

        return result

    def save_results(self, result: BenchmarkResult, output_path: str):
        """Save benchmark results to JSON file."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to: {output_path}")

    def run_all_benchmarks(
        self,
        adapters: Optional[List[str]] = None,
        output_dir: str = 'results'
    ) -> List[BenchmarkResult]:
        """
        Run benchmarks for all specified adapters.

        Args:
            adapters: List of adapter names to run, or None for all
            output_dir: Directory to save results

        Returns:
            List of BenchmarkResult objects
        """
        # Load dataset
        self.load_dataset()

        # Default to all adapters
        if adapters is None or 'all' in adapters:
            adapters = list(self.DEFAULT_CONFIGS.keys())

        # Adapter class mapping
        adapter_classes = {
            'cortex': CortexAdapter,
            'engram': EngramAdapter,
            'openclaw_engram': OpenClawEngramAdapter
        }

        results = []
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        for adapter_name in adapters:
            if adapter_name not in adapter_classes:
                print(f"Unknown adapter: {adapter_name}")
                continue

            try:
                config = self.DEFAULT_CONFIGS.get(adapter_name, {})
                result = self.run_adapter_benchmark(
                    adapter_name=adapter_name,
                    adapter_class=adapter_classes[adapter_name],
                    config=config
                )

                # Save individual results
                output_path = os.path.join(output_dir, f'{adapter_name}_results.json')
                self.save_results(result, output_path)

                results.append(result)

            except Exception as e:
                print(f"Error running benchmark for {adapter_name}: {e}")
                import traceback
                traceback.print_exc()

        # Save combined summary
        self._save_summary(results, output_dir, timestamp)

        return results

    def _save_summary(self, results: List[BenchmarkResult], output_dir: str, timestamp: str):
        """Save a summary of all benchmark results."""
        summary = {
            'timestamp': timestamp,
            'benchmark_version': '1.0.0',
            'dataset': 'locomo10',
            'total_questions': len(self.qa_pairs),
            'results': [
                {
                    'adapter': r.adapter_name,
                    'accuracy': r.accuracy,
                    'average_latency_ms': r.average_latency_ms,
                    'recall': r.recall,
                    'f1_score': r.f1_score,
                    'error_count': r.error_count
                }
                for r in results
            ]
        }

        summary_path = os.path.join(output_dir, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\nSummary saved to: {summary_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='LoCoMo Memory Benchmark Runner')
    parser.add_argument(
        '--adapter', '-a',
        nargs='+',
        default=['all'],
        help='Adapter(s) to benchmark (cortex, engram, openclaw_engram, or all)'
    )
    parser.add_argument(
        '--output', '-o',
        default='results',
        help='Output directory for results'
    )
    parser.add_argument(
        '--data', '-d',
        default='data/locomo10.json',
        help='Path to LoCoMo dataset'
    )

    args = parser.parse_args()

    print("="*60)
    print("LoCoMo Memory Benchmark Suite")
    print("="*60)

    runner = BenchmarkRunner(data_path=args.data)
    results = runner.run_all_benchmarks(
        adapters=args.adapter,
        output_dir=args.output
    )

    print("\n" + "="*60)
    print("ALL BENCHMARKS COMPLETE")
    print("="*60)

    if results:
        print("\nFinal Comparison:")
        print("-"*60)
        print(f"{'Adapter':<20} {'Accuracy':<12} {'Latency':<12} {'F1':<8}")
        print("-"*60)
        for r in results:
            print(f"{r.adapter_name:<20} {r.accuracy*100:>6.1f}%      {r.average_latency_ms:>6.1f}ms     {r.f1_score:.3f}")
        print("-"*60)


if __name__ == '__main__':
    main()
