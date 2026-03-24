"""
LoCoMo Benchmark Runner

This module implements the LoCoMo benchmark for evaluating memory systems.
LoCoMo = Long Context Memory benchmark using conversation data.

Dataset format (locomo10.json):
- Each item is a conversation with:
  - conversation: array of dialogue turns
  - qa: array of {question, answer, evidence, category}
  - event_summary, observation, session_summary: metadata
"""

import os
import sys
import json
import time
import random
import argparse
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
from datetime import datetime

# Import adapters
try:
    from cortex_adapter import CortexAdapter
    from engram_adapter import EngramAdapter
    from openclaw_engram_adapter import OpenClawEngramAdapter
except ImportError as e:
    print(f"Warning: Could not import adapters: {e}")


@dataclass
class ConversationQAPair:
    """Single QA pair from a conversation."""
    sample_id: str
    conversation_turns: List[Dict]  # Full conversation for context
    question: str
    answer: str
    evidence: List[str]
    category: int


class LoCoMoBenchmarkRunner:
    """Benchmark runner for LoCoMo dataset."""

    ADAPTERS = {
        'cortex': CortexAdapter,
        'engram': EngramAdapter,
        'openclaw_engram': OpenClawEngramAdapter,
    }

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

    SEED = 42

    def __init__(self, data_path: str = 'data/locomo10.json'):
        self.data_path = data_path
        self.conversations: List[Dict] = []
        self.qa_pairs: List[ConversationQAPair] = []
        self.seed(self.SEED)

    def seed(self, value: int):
        random.seed(value)

    def load_dataset(self) -> List[ConversationQAPair]:
        """Load the LoCoMo dataset properly matching the actual format."""
        print(f"Loading dataset from {self.data_path}...")

        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Dataset not found: {self.data_path}")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict) and 'data' in data:
            data = data['data']

        self.conversations = data
        self.qa_pairs = []

        for conv in data:
            sample_id = conv.get('sample_id', 'unknown')
            conversation_turns = conv.get('conversation', [])
            qa_list = conv.get('qa', [])

            for qa_item in qa_list:
                pair = ConversationQAPair(
                    sample_id=sample_id,
                    conversation_turns=conversation_turns,
                    question=qa_item.get('question', ''),
                    answer=qa_item.get('answer', ''),
                    evidence=qa_item.get('evidence', []),
                    category=qa_item.get('category', 0)
                )
                self.qa_pairs.append(pair)

        print(f"Loaded {len(self.conversations)} conversations with {len(self.qa_pairs)} total QA pairs")
        return self.qa_pairs

    def build_context(self, conversation_data: Dict) -> List[str]:
        """Build facts from conversation dict for ingestion."""
        facts = []
        
        # Handle session-based structure
        session_keys = [k for k in conversation_data.keys() 
                       if k.startswith('session_') and '_date_time' not in k]
        
        for session_key in sorted(session_keys):
            turns = conversation_data.get(session_key, [])
            for turn in turns:
                if isinstance(turn, dict):
                    speaker = turn.get('speaker', '')
                    text = turn.get('text', '')
                    if text:
                        facts.append(f"[{speaker}]: {text}")
        
        # Also include summaries if available
        if conversation_data.get('event_summary'):
            facts.append(f"[Event Summary]: {conversation_data['event_summary']}")
        if conversation_data.get('session_summary'):
            facts.append(f"[Session Summary]: {conversation_data['session_summary']}")
        
        return facts

    def evaluate_answer(self, predicted: str, expected) -> bool:
        """Evaluate if predicted answer matches expected."""
        if not predicted:
            return False
        
        # Convert expected to string if it's not
        if not isinstance(expected, str):
            expected = str(expected)
        
        if not expected:
            return False

        pred_norm = predicted.lower().strip()
        exp_norm = expected.lower().strip()

        if pred_norm == exp_norm:
            return True

        similarity = SequenceMatcher(None, pred_norm, exp_norm).ratio()
        if similarity >= 0.8:
            return True

        if exp_norm in pred_norm or pred_norm in exp_norm:
            return True

        return False

    def run_benchmark(
        self,
        adapter_name: str,
        adapter_class,
        config: Dict,
        output_path: str = 'results',
        warm_up: int = 3
    ) -> Dict:
        """Run benchmark for a single adapter."""
        print(f"\n{'='*60}")
        print(f"Benchmark: {adapter_name}")
        print(f"{'='*60}")

        adapter = adapter_class(config)

        # Health check
        print(f"Health check: ", end='')
        if adapter.health_check():
            print("OK")
        else:
            print("FAILED - continuing anyway")

        # Clear existing data
        print("Clearing existing data...")
        adapter.clear()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = os.path.join(output_path, f'{adapter_name}_results_{timestamp}.json')
        os.makedirs(output_path, exist_ok=True)

        all_results = []
        category_stats = {}

        # Process each conversation as a unit
        for conv_idx, conv in enumerate(self.conversations):
            conversation_data = conv.get('conversation', {})
            qa_list = conv.get('qa', [])

            if not conversation_data or not qa_list:
                continue

            # Ingest conversation facts (limit to 10 for performance)
            facts = self.build_context(conversation_data)[:10]
            if facts:
                adapter.ingest(facts)

            # Answer questions for this conversation
            for qa in qa_list:
                question = qa.get('question', '')
                expected = qa.get('answer', '')
                category = qa.get('category', 0)

                if not question:
                    continue

                start = time.time()
                predicted, _ = adapter.query(question)
                latency_ms = (time.time() - start) * 1000

                correct = self.evaluate_answer(predicted, expected)

                result = {
                    'sample_id': conv.get('sample_id', 'unknown'),
                    'conversation_idx': conv_idx,
                    'question': question,
                    'expected': expected,
                    'predicted': predicted,
                    'correct': correct,
                    'latency_ms': latency_ms,
                    'category': category
                }
                all_results.append(result)

                # Track by category
                cat_key = f'category_{category}'
                if cat_key not in category_stats:
                    category_stats[cat_key] = {'total': 0, 'correct': 0}
                category_stats[cat_key]['total'] += 1
                category_stats[cat_key]['correct'] += int(correct)

            if (conv_idx + 1) % 5 == 0:
                print(f"  Processed {conv_idx + 1}/{len(self.conversations)} conversations")

        # Calculate metrics
        total = len(all_results)
        correct = sum(1 for r in all_results if r['correct'])
        accuracy = correct / total if total > 0 else 0

        latencies = [r['latency_ms'] for r in all_results]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        metrics = {
            'adapter': adapter_name,
            'timestamp': timestamp,
            'total_questions': total,
            'correct_answers': correct,
            'accuracy': accuracy,
            'average_latency_ms': avg_latency,
            'category_stats': category_stats,
            'results': all_results
        }

        # Save results
        with open(results_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"\nResults saved to: {results_file}")

        print(f"\n--- SUMMARY ---")
        print(f"Accuracy: {accuracy:.2%} ({correct}/{total})")
        print(f"Avg latency: {avg_latency:.2f}ms")

        return metrics


def main():
    parser = argparse.ArgumentParser(description='LoCoMo Memory Benchmark')
    parser.add_argument('--adapter', default='cortex',
                        choices=['cortex', 'engram', 'openclaw_engram', 'all'],
                        help='Adapter to benchmark')
    parser.add_argument('--output', default='results',
                        help='Output directory for results')
    parser.add_argument('--warm-up', type=int, default=3,
                        help='Number of warm-up queries')
    args = parser.parse_args()

    runner = LoCoMoBenchmarkRunner()
    runner.load_dataset()

    if args.adapter == 'all':
        adapters_to_run = runner.ADAPTERS.keys()
    else:
        adapters_to_run = [args.adapter]

    for adapter_name in adapters_to_run:
        if adapter_name not in runner.ADAPTERS:
            print(f"Unknown adapter: {adapter_name}")
            continue

        adapter_class = runner.ADAPTERS[adapter_name]
        config = runner.DEFAULT_CONFIGS.get(adapter_name, {})

        try:
            runner.run_benchmark(
                adapter_name=adapter_name,
                adapter_class=adapter_class,
                config=config,
                output_path=args.output,
                warm_up=args.warm_up
            )
        except Exception as e:
            print(f"Benchmark failed for {adapter_name}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()
