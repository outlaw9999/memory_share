# 🧠 .kit (memory_share)

**The SQLite for AI Agent Memory.** `.kit` is a deterministic, zero-dependency, and LLM-agnostic memory engine. It is not an agent framework. It is the core infrastructure that gives your AI agents a persistent, deterministic *Hippocampus*.

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Status: v2.0 Core Engine](https://img.shields.io/badge/Status-v2.0_SAM_Epoch-red.svg)]()

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
- [ARCHITECTURE.md](ARCHITECTURE.md): The Engine-First philosophy & SAM Schema.
- [examples/minimal_example.py](examples/minimal_example.py): A ready-to-run verification script.

### 🔄 Migration from v1.3.1
`.kit v2.0` introduces the **Structured Agent Memory (SAM)** architecture, transitioning from a code-analysis engine to a universal agent memory kernel.
- **Historical Code:** The legacy AST/Git analysis logic is preserved in the `plugin/kit-ext-git` branch and tagged as `v1.3.1`.
- **Core Pivot:** v2.0 focuses on deterministic fact retrieval, ranking, and graph expansion for AI assistants.

---
*Built for IDEs, Agents, and the Open-Source Community to fork.*
