# 🧠 .kit (memory_share)

**The SQLite for AI Agent Memory.** `.kit` is a deterministic, zero-dependency, and LLM-agnostic memory engine. It is not an agent framework. It is the core infrastructure that gives your AI agents a persistent, deterministic *Hippocampus*.

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Status: v1.0 Core Engine](https://img.shields.io/badge/Status-v1.0_Engine_Frozen-red.svg)]()

### ⚡ Why .kit?
Vector DBs are for probabilistic search. `.kit` is for **absolute ground truth**.
- **Deterministic:** Backed by an immutable SQLite Graph. No hallucinated memories.
- **LLM-Agnostic:** Stores raw facts, not model-specific embeddings. Survive the LLM wars.
- **Cognitive Decay:** Built-in heuristic ranking (Spaced Repetition) to prevent context bloat.
- **Local-First:** 100% private. Runs entirely on your machine.

### 📦 Minimal Example
```python
from pathlib import Path
from kit.api import init_kernel, learn, recall

init_kernel(Path("memory.db"))

# 1. Ingest an immutable fact
learn("auth_system", "architecture", "JWT uses HS256 algorithm")

# 2. Recall with 1-hop graph expansion & heuristic ranking
memories = recall(["auth_system"], limit=5)

for m in memories:
    print(f"[{m.entity_uid}] -> {m.content}")
```

### 📖 Documentation
Read the [ARCHITECTURE.md](ARCHITECTURE.md) to understand the Engine-First philosophy, the Immutable Fact Ledger, and the Stable API Boundary.

---
*Built for IDEs, Agents, and the Open-Source Community to fork.*
