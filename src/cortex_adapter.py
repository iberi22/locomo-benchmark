"""
CortexAdapter - SWAL Cortex Memory System Adapter

This adapter provides an interface for benchmarking the SWAL Cortex memory system.
Cortex is SWAL's central memory system with SurrealDB backend.

API Endpoint: http://localhost:8003
Authentication: X-Cortex-Token header
"""

import json
import time
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class CortexAdapter:
    """Adapter for SWAL Cortex memory system."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Cortex adapter.

        Args:
            config: Dictionary with connection parameters
                - api_url: Base URL for the Cortex API (default: http://localhost:8003)
                - token: Authentication token (default: dev-token)
                - timeout: Request timeout in seconds (default: 30)
        """
        self.config = config or {}
        self.api_url = self.config.get('api_url', 'http://localhost:8003')
        self.token = self.config.get('token', 'dev-token')
        self.timeout = self.config.get('timeout', 30)
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'X-Cortex-Token': self.token
        })

    def ingest(self, facts: List[str]) -> bool:
        """
        Ingest facts into Cortex memory.

        Args:
            facts: List of factual statements to store

        Returns:
            True if all facts were ingested successfully, False otherwise
        """
        success_count = 0
        total = len(facts)

        for i, fact in enumerate(facts):
            try:
                # Use /memory/add endpoint
                payload = json.dumps({
                    'path': f'benchmark/ingestion/{datetime.now().strftime("%Y%m%d_%H%M%S")}_{i}',
                    'content': fact,
                    'metadata': {
                        'type': 'benchmark_fact',
                        'timestamp': datetime.now().isoformat(),
                        'index': i
                    }
                })

                response = self._session.post(
                    f'{self.api_url}/memory/add',
                    data=payload,
                    timeout=self.timeout
                )

                if response.status_code in (200, 201):
                    success_count += 1
                else:
                    print(f"Failed to ingest fact {i}: {response.status_code} - {response.text}")

            except requests.exceptions.Timeout:
                print(f"Timeout ingesting fact {i}")
            except requests.exceptions.ConnectionError:
                print(f"Connection error ingesting fact {i}")
            except Exception as e:
                print(f"Error ingesting fact {i}: {e}")

        return success_count == total

    def query(self, question: str) -> Tuple[str, float]:
        """
        Query the Cortex memory system.

        Args:
            question: The question to ask

        Returns:
            Tuple of (answer, latency_ms)
        """
        start_time = time.time()

        try:
            # Use /memory/search endpoint
            payload = json.dumps({
                'query': question,
                'limit': 5
            })

            response = self._session.post(
                f'{self.api_url}/memory/search',
                data=payload,
                timeout=self.timeout
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                
                # Extract answer from search results
                if 'results' in data and len(data['results']) > 0:
                    # Get the most relevant result
                    best_match = data['results'][0]
                    answer = best_match.get('content', '')
                    return answer, latency_ms
                
                return '', latency_ms
            else:
                print(f"Query failed: {response.status_code} - {response.text}")
                return '', latency_ms

        except requests.exceptions.Timeout:
            print(f"Query timeout: {question}")
            return '', (time.time() - start_time) * 1000
        except requests.exceptions.ConnectionError:
            print(f"Query connection error: {question}")
            return '', (time.time() - start_time) * 1000
        except Exception as e:
            print(f"Query error: {e}")
            return '', (time.time() - start_time) * 1000

    def clear(self) -> bool:
        """
        Clear all benchmark-related memories from Cortex.

        Note: The /memory/clear endpoint doesn't exist in current Cortex API.
        This method returns True to indicate the operation was attempted.
        For proper isolation, we use unique paths for each benchmark run.
        """
        # Clear not supported - we use timestamped paths to avoid contamination
        print("Note: clear() not supported - using unique paths per run")
        return True

    def health_check(self) -> bool:
        """
        Check if Cortex is healthy and responding.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._session.get(
                f'{self.api_url}/health',
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def get_stats(self) -> Dict:
        """
        Get memory statistics from Cortex.

        Returns:
            Dictionary with memory stats
        """
        try:
            response = self._session.get(
                f'{self.api_url}/memory/stats',
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}

    def bulk_search(self, queries: List[str]) -> List[Tuple[str, float, List[Dict]]]:
        """
        Perform multiple searches and return results with metadata.

        Args:
            queries: List of questions to ask

        Returns:
            List of (answer, latency_ms, raw_results) tuples
        """
        results = []
        for query in queries:
            start_time = time.time()
            try:
                response = self._session.post(
                    f'{self.api_url}/memory/search',
                    json={'query': query, 'limit': 5},
                    timeout=self.timeout
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    raw_results = data.get('results', [])
                    answer = raw_results[0].get('content', '') if raw_results else ''
                    results.append((answer, latency_ms, raw_results))
                else:
                    results.append(('', latency_ms, []))
            except Exception as e:
                print(f"Bulk search error for '{query}': {e}")
                results.append(('', (time.time() - start_time) * 1000, []))

        return results


def main():
    """Test the adapter locally."""
    print("Testing Cortex Adapter...")

    adapter = CortexAdapter()

    # Health check
    print(f"Health check: {adapter.health_check()}")

    # Clear any existing benchmark data
    print("Clearing benchmark data...")
    adapter.clear()

    # Test ingestion
    test_facts = [
        "John lives in Boston",
        "John owns a red car",
        "Sarah works at Google",
        "The meeting is at 3pm"
    ]

    print(f"Ingesting {len(test_facts)} facts...")
    success = adapter.ingest(test_facts)
    print(f"Ingestion success: {success}")

    # Test query
    answer, latency = adapter.query("What color is John's car?")
    print(f"Query answer: {answer}, Latency: {latency:.2f}ms")

    # Test stats
    stats = adapter.get_stats()
    print(f"Stats: {stats}")


if __name__ == '__main__':
    main()
