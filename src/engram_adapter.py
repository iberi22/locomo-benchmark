"""
EngramAdapter - Gentleman-Programming/engram Memory System Adapter

This adapter provides an interface for benchmarking the Engram memory system
from Gentleman-Programming.

API Endpoint: http://localhost:8080 (configurable)
Documentation: https://github.com/Gentleman-Programming/engram
"""

import json
import time
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class EngramAdapter:
    """Adapter for Gentleman-Programming/engram memory system."""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Engram adapter.

        Args:
            config: Dictionary with connection parameters
                - api_url: Base URL for the Engram API (default: http://localhost:8080)
                - api_key: Optional API key for authentication
                - timeout: Request timeout in seconds (default: 30)
                - vault_id: Optional vault ID for multi-vault setups
        """
        self.config = config or {}
        self.api_url = self.config.get('api_url', 'http://localhost:8080')
        self.api_key = self.config.get('api_key', '')
        self.timeout = self.config.get('timeout', 30)
        self.vault_id = self.config.get('vault_id', 'default')
        self._session = requests.Session()
        
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        self._session.headers.update(headers)

    def ingest(self, facts: List[str]) -> bool:
        """
        Ingest facts into Engram memory.

        Args:
            facts: List of factual statements to store

        Returns:
            True if all facts were ingested successfully, False otherwise
        """
        success_count = 0
        total = len(facts)

        for i, fact in enumerate(facts):
            try:
                # Engram uses /api/notes or similar endpoint
                # Based on engram's API structure
                payload = {
                    'title': f'Fact_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{i}',
                    'content': fact,
                    'tags': ['benchmark', 'memory-test'],
                    'vaultId': self.vault_id,
                    'metadata': {
                        'type': 'benchmark_fact',
                        'timestamp': datetime.now().isoformat(),
                        'index': i
                    }
                }

                response = self._session.post(
                    f'{self.api_url}/api/notes',
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code in (200, 201, 204):
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
        Query the Engram memory system.

        Args:
            question: The question to ask

        Returns:
            Tuple of (answer, latency_ms)
        """
        start_time = time.time()

        try:
            # Engram search endpoint
            payload = {
                'query': question,
                'vaultId': self.vault_id,
                'limit': 5
            }

            response = self._session.post(
                f'{self.api_url}/api/search',
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
                
                # Alternative response structure
                if 'notes' in data and len(data['notes']) > 0:
                    answer = data['notes'][0].get('content', '')
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
        Clear all benchmark-related memories from Engram.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete all notes with benchmark tag
            response = self._session.delete(
                f'{self.api_url}/api/notes',
                params={'tag': 'benchmark', 'vaultId': self.vault_id},
                timeout=self.timeout
            )
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"Clear error: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check if Engram is healthy and responding.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._session.get(
                f'{self.api_url}/api/health',
                timeout=5
            )
            return response.status_code == 200
        except:
            # Try alternative health endpoint
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
        Get memory statistics from Engram.

        Returns:
            Dictionary with memory stats
        """
        try:
            response = self._session.get(
                f'{self.api_url}/api/stats',
                params={'vaultId': self.vault_id},
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
                    f'{self.api_url}/api/search',
                    json={'query': query, 'vaultId': self.vault_id, 'limit': 5},
                    timeout=self.timeout
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    raw_results = data.get('results', data.get('notes', []))
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
    print("Testing Engram Adapter...")

    adapter = EngramAdapter()

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
