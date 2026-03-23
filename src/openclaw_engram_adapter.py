"""
OpenClawEngramAdapter - joshuaswarren/openclaw-engram Memory System Adapter

This adapter provides an interface for benchmarking the OpenClaw Engram memory system,
which is joshuaswarren's adapter for using Engram with OpenClaw.

API Endpoint: http://localhost:8081 (configurable)
Repository: https://github.com/joshuaswarren/openclaw-engram
"""

import json
import time
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class OpenClawEngramAdapter:
    """Adapter for joshuaswarren/openclaw-engram memory system."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the OpenClaw Engram adapter.

        Args:
            config: Dictionary with connection parameters
                - api_url: Base URL for the OpenClaw Engram API (default: http://localhost:8081)
                - api_key: Optional API key for authentication
                - timeout: Request timeout in seconds (default: 30)
                - user_id: Optional user ID for multi-user setups
        """
        self.config = config or {}
        self.api_url = self.config.get('api_url', 'http://localhost:8081')
        self.api_key = self.config.get('api_key', '')
        self.timeout = self.config.get('timeout', 30)
        self.user_id = self.config.get('user_id', 'benchmark-user')
        self._session = requests.Session()
        
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        self._session.headers.update(headers)

    def ingest(self, facts: List[str]) -> bool:
        """
        Ingest facts into OpenClaw Engram memory.

        Args:
            facts: List of factual statements to store

        Returns:
            True if all facts were ingested successfully, False otherwise
        """
        success_count = 0
        total = len(facts)

        # OpenClaw Engram might batch ingest
        batch_payload = {
            'userId': self.user_id,
            'facts': [
                {
                    'content': fact,
                    'metadata': {
                        'type': 'benchmark_fact',
                        'timestamp': datetime.now().isoformat(),
                        'index': i
                    }
                }
                for i, fact in enumerate(facts)
            ]
        }

        try:
            # Try batch ingestion first
            response = self._session.post(
                f'{self.api_url}/api/memory/batch',
                json=batch_payload,
                timeout=self.timeout
            )

            if response.status_code in (200, 201):
                success_count = total
            else:
                # Fall back to individual ingestion
                for i, fact in enumerate(facts):
                    if self._ingest_single(fact, i):
                        success_count += 1

        except requests.exceptions.Timeout:
            print("Batch ingestion timeout, falling back to single ingestion")
            for i, fact in enumerate(facts):
                if self._ingest_single(fact, i):
                    success_count += 1
        except requests.exceptions.ConnectionError:
            print("Connection error in batch ingestion, falling back to single")
            for i, fact in enumerate(facts):
                if self._ingest_single(fact, i):
                    success_count += 1
        except Exception as e:
            print(f"Batch ingestion error: {e}, falling back to single")
            for i, fact in enumerate(facts):
                if self._ingest_single(fact, i):
                    success_count += 1

        return success_count == total

    def _ingest_single(self, fact: str, index: int) -> bool:
        """
        Ingest a single fact into memory.

        Args:
            fact: The factual statement to store
            index: Index for ordering

        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {
                'userId': self.user_id,
                'content': fact,
                'metadata': {
                    'type': 'benchmark_fact',
                    'timestamp': datetime.now().isoformat(),
                    'index': index
                }
            }

            response = self._session.post(
                f'{self.api_url}/api/memory/add',
                json=payload,
                timeout=self.timeout
            )

            return response.status_code in (200, 201, 204)
        except:
            return False

    def query(self, question: str) -> Tuple[str, float]:
        """
        Query the OpenClaw Engram memory system.

        Args:
            question: The question to ask

        Returns:
            Tuple of (answer, latency_ms)
        """
        start_time = time.time()

        try:
            payload = {
                'userId': self.user_id,
                'query': question,
                'limit': 5
            }

            response = self._session.post(
                f'{self.api_url}/api/memory/search',
                json=payload,
                timeout=self.timeout
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                
                # Extract answer from search results
                if 'results' in data and len(data['results']) > 0:
                    best_match = data['results'][0]
                    answer = best_match.get('content', '')
                    return answer, latency_ms
                
                # Alternative response structures
                if 'memories' in data and len(data['memories']) > 0:
                    answer = data['memories'][0].get('content', '')
                    return answer, latency_ms
                
                if 'facts' in data and len(data['facts']) > 0:
                    answer = data['facts'][0].get('content', '')
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
        Clear all benchmark-related memories from OpenClaw Engram.

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self._session.delete(
                f'{self.api_url}/api/memory/clear',
                params={'userId': self.user_id},
                timeout=self.timeout
            )
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"Clear error: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check if OpenClaw Engram is healthy and responding.

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
            try:
                response = self._session.get(
                    f'{self.api_url}/api/health',
                    timeout=5
                )
                return response.status_code == 200
            except:
                return False

    def get_stats(self) -> Dict:
        """
        Get memory statistics from OpenClaw Engram.

        Returns:
            Dictionary with memory stats
        """
        try:
            response = self._session.get(
                f'{self.api_url}/api/memory/stats',
                params={'userId': self.user_id},
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
                    f'{self.api_url}/api/memory/search',
                    json={'userId': self.user_id, 'query': query, 'limit': 5},
                    timeout=self.timeout
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    raw_results = data.get('results', data.get('memories', data.get('facts', [])))
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
    print("Testing OpenClaw Engram Adapter...")

    adapter = OpenClawEngramAdapter()

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
