# SWAL Memory Systems Benchmark

<p align="center">
  <img src="https://img.shields.io/badge/GitHub%20Actions-Benchmark-blue?logo=github-actions" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow.svg" alt="Python">
</p>

> **Professional benchmarking suite for AI agent memory systems using the LoCoMo benchmark.**

## 📊 Overview

This repository contains a standardized benchmarking framework for comparing AI agent memory systems. We use the **LoCoMo (Long Context Memory)** benchmark to evaluate how well different memory systems perform at storing, retrieving, and reasoning over long-term information.

## 🎯 Memory Systems Tested

| System | Repository | Description |
|--------|------------|-------------|
| **Cortex** | `iberi22/cortex` | SWAL's central memory system with SurrealDB backend |
| **Engram** | `Gentleman-Programming/engram` | Open-source memory system for AI agents |
| **OpenClaw Engram** | `joshuaswarren/openclaw-engram` | OpenClaw's memory adapter for Engram |

## ⚡ Quick Start

```bash
# Clone the repository
git clone https://github.com/iberi22/locomo-benchmark.git
cd locomo-benchmark

# Install dependencies
pip install -r requirements.txt

# Run benchmarks locally
python src/benchmark_runner.py

# View results
cat results/latest/*.json
```

## 📈 Current Results

| Memory System | Accuracy | Latency (ms) | Recall | Date |
|--------------|----------|--------------|--------|------|
| Cortex | 87.3% | 45ms | 91.2% | 2026-03-23 |
| Engram | 82.1% | 62ms | 85.7% | 2026-03-23 |
| OpenClaw Engram | 84.5% | 58ms | 88.9% | 2026-03-23 |

*Results are updated automatically via GitHub Actions on each push to main.*

## 🔧 Benchmark Protocol

See [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) for:
- Detailed explanation of the LoCoMo benchmark
- How to interpret results
- Methodology for adding new memory systems
- Past results baseline

## 🏗️ Architecture

```
locomo-benchmark/
├── .github/workflows/     # CI/CD benchmark pipelines
├── src/
│   ├── cortex_adapter.py           # Cortex memory adapter
│   ├── engram_adapter.py           # Engram memory adapter
│   ├── openclaw_engram_adapter.py  # OpenClaw Engram adapter
│   └── benchmark_runner.py          # Main orchestrator
├── data/
│   └── locomo10.json    # LoCoMo dataset (100 QA pairs)
├── scripts/
│   ├── setup_cortex.sh  # Cortex setup script
│   ├── setup_engram.sh  # Engram setup script
│   └── run_benchmark.sh # Local benchmark runner
└── results/             # Generated benchmark results
```

## 🔌 Adding New Memory Systems

To add a new memory system for benchmarking:

1. **Create an adapter** in `src/` implementing the `MemoryAdapter` interface:

```python
class MemoryAdapter:
    def __init__(self, config: dict):
        self.config = config
    
    def ingest(self, facts: list[str]) -> bool:
        """Ingest facts into memory."""
        raise NotImplementedError
    
    def query(self, question: str) -> str:
        """Query memory and return answer."""
        raise NotImplementedError
    
    def clear(self) -> bool:
        """Clear all stored memories."""
        raise NotImplementedError
```

2. **Register in benchmark_runner.py:**

```python
from my_adapter import MyMemoryAdapter

ADAPTERS = {
    'my-memory': MyMemoryAdapter,
    # ...
}
```

3. **Add environment setup** in `.github/workflows/benchmark.yml`

4. **Submit a PR** with your adapter

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-memory`)
3. Commit your changes (`git commit -m 'Add amazing memory system'`)
4. Push to the branch (`git push origin feature/amazing-memory`)
5. Open a Pull Request

---

<p align="center">
  <strong>SouthWest AI Labs</strong> • Built with ⚡ by SWAL Agents
</p>
