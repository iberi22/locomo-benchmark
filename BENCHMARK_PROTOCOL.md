# LoCoMo Benchmark Protocol

## 📖 What is LoCoMo?

**LoCoMo (Long Context Memory)** is a benchmark designed to evaluate AI agent memory systems on their ability to:

1. **Store** factual information over extended periods
2. **Retrieve** relevant facts when queried
3. **Reason** across multiple stored facts to answer complex questions

### Dataset Structure

The benchmark uses `locomo10.json` containing **100 QA pairs** across categories:

| Category | Count | Example |
|----------|-------|---------|
| Factual Recall | 30 | "What color is John's car?" |
| Temporal Reasoning | 25 | "What did Sarah do after the meeting?" |
| Multi-hop Inference | 25 | "Who was the manager of Mary's team?" |
| Contradiction Detection | 20 | "Was there any conflict in the travel plans?" |

Each QA pair contains:
```json
{
  "id": "locomo_001",
  "category": "factual_recall",
  "context": ["John owns a red car", "John lives in Boston"],
  "question": "What color is John's car?",
  "answer": "red",
  "difficulty": "easy"
}
```

## 📊 Interpreting Results

### Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Accuracy** | % of questions answered correctly | > 85% |
| **Latency** | Average response time in milliseconds | < 100ms |
| **Recall** | % of stored facts successfully retrieved | > 90% |
| **F1 Score** | Harmonic mean of precision and recall | > 0.85 |

### Performance Tiers

| Tier | Accuracy | Latency | Description |
|------|----------|---------|-------------|
| 🥇 Gold | ≥ 90% | < 50ms | Production-ready, excellent performance |
| 🥈 Silver | ≥ 80% | < 100ms | Good performance, suitable for most use cases |
| 🥉 Bronze | ≥ 70% | < 200ms | Acceptable, room for improvement |
| ⚠️ Below Standard | < 70% | ≥ 200ms | Needs significant work |

### Result Files

Results are stored in `results/` with timestamps:
```
results/
├── 2026-03-23_14-30-00/
│   ├── cortex_results.json
│   ├── engram_results.json
│   └── openclaw_engram_results.json
└── latest/
    └── (symlinks to most recent)
```

## 🔬 Methodology

### Benchmark Process

1. **Setup Phase**
   - Initialize memory system with default configuration
   - Clear any existing data

2. **Ingestion Phase**
   - Load all context facts from `locomo10.json`
   - Ingest facts in random order
   - Measure ingestion time and success rate

3. **Query Phase**
   - For each QA pair:
     - Present question to memory system
     - Capture response and latency
     - Compare against expected answer
   - Calculate aggregate metrics

4. **Reporting Phase**
   - Generate JSON results
   - Update leaderboard
   - Publish artifacts

### Answer Evaluation

Answers are evaluated using:
- **Exact match** for simple factual answers
- **Semantic similarity** (cosine similarity > 0.85) for complex answers
- **Case-insensitive** comparison

## 🔌 Adding New Memory Systems

### 1. Create the Adapter

Create a new file in `src/` following this template:

```python
"""
MyMemoryAdapter - Adapter for My Memory System
"""
import requests
import time
from typing import List, Dict, Optional

class MyMemoryAdapter:
    """Adapter for MyMemory memory system."""

    def __init__(self, config: Dict):
        """
        Initialize the adapter.
        
        Args:
            config: Dictionary with connection parameters
                - api_url: Base URL for the memory API
                - api_key: Optional API key
                - timeout: Request timeout in seconds
        """
        self.api_url = config.get('api_url', 'http://localhost:8000')
        self.api_key = config.get('api_key', '')
        self.timeout = config.get('timeout', 30)

    def ingest(self, facts: List[str]) -> bool:
        """
        Ingest facts into memory.
        
        Args:
            facts: List of factual statements to store
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        try:
            for fact in facts:
                response = requests.post(
                    f"{self.api_url}/memory/add",
                    json={'content': fact},
                    headers=self._headers(),
                    timeout=self.timeout
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception as e:
            print(f"Ingestion error: {e}")
            return False

    def query(self, question: str) -> tuple[str, float]:
        """
        Query the memory system.
        
        Args:
            question: The question to ask
            
        Returns:
            Tuple of (answer, latency_ms)
        """
        start_time = time.time()
        try:
            response = requests.post(
                f"{self.api_url}/memory/search",
                json={'query': question},
                headers=self._headers(),
                timeout=self.timeout
            )
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                return data.get('answer', ''), latency
            return '', latency
        except Exception as e:
            print(f"Query error: {e}")
            return '', (time.time() - start_time) * 1000

    def clear(self) -> bool:
        """Clear all memories."""
        try:
            response = requests.post(
                f"{self.api_url}/memory/clear",
                headers=self._headers(),
                timeout=self.timeout
            )
            return response.status_code == 200
        except:
            return False

    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
```

### 2. Register in benchmark_runner.py

```python
# Add import
from my_memory_adapter import MyMemoryAdapter

# Add to ADAPTERS dict
ADAPTERS = {
    'cortex': CortexAdapter,
    'engram': EngramAdapter,
    'openclaw_engram': OpenClawEngramAdapter,
    'my_memory': MyMemoryAdapter,  # Add here
}
```

### 3. Configure Environment

Add environment setup in `.github/workflows/benchmark.yml`:

```yaml
- name: Setup MyMemory
  run: |
    # Your setup commands
    docker pull mymemory/image:latest
    docker run -d -p 9000:8000 mymemory/image:latest
    sleep 5  # Wait for startup
```

### 4. Test Locally

```bash
# Run benchmark with your adapter
python src/benchmark_runner.py --adapter my_memory
```

## 📋 Past Results Baseline

### Historical Performance

| Date | Cortex | Engram | OpenClaw Engram |
|------|--------|--------|-----------------|
| 2026-03-23 | 87.3% / 45ms / 91.2% | 82.1% / 62ms / 85.7% | 84.5% / 58ms / 88.9% |
| 2026-03-16 | 86.8% / 48ms / 90.5% | 81.5% / 65ms / 84.2% | 83.9% / 61ms / 87.5% |
| 2026-03-09 | 85.2% / 52ms / 89.8% | 80.9% / 68ms / 83.1% | 82.7% / 64ms / 86.2% |

*Format: Accuracy / Latency / Recall*

### Trend Analysis

- **Cortex**: Consistent improvement (+2.1% accuracy over 2 weeks)
- **Engram**: Stable performance, slight improvements
- **OpenClaw Engram**: Steady gains in accuracy (+1.8% over 2 weeks)

## 🔒 Reproducibility

To ensure reproducible results:

1. **Fixed seed**: All random operations use seed `42`
2. **Warm-up runs**: 3 warm-up queries before timing
3. **Environment isolation**: Each adapter runs in isolated environment
4. **Statistical significance**: Results include 95% confidence intervals

## 📞 Contact

For questions about the benchmark protocol:
- GitHub Issues: [iberi22/locomo-benchmark/issues](https://github.com/iberi22/locomo-benchmark/issues)
- Email: sebastian@swal.dev

---

*Protocol Version: 1.0.0 | Last Updated: 2026-03-23*
