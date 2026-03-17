# 📖 .kit Reference Guide (v1.0.0)

This guide provides a minimal reference for the `.kit` Python API and CLI interface.

## 🐍 Python API (`kit/api.py`)

### 1. Bootstrap
```python
from kit import api
from pathlib import Path

api.init_kernel(Path(".kit/brain.db"))
```

### 2. Core Functions
- **`learn(uid, kind, content, importance=0.5, tag='decision')`**: Inject a new fact into memory.
- **`recall(query_string, limit=15)`**: Retrieve the most relevant memories for a context string.
- **`reflect(signal)`**: Analyze a code signal against persistent invariants.
- **`export_prompt(query, budget=1000)`**: Format retrieved memories for an LLM system prompt.

---

## 💻 CLI Interface

### Initialization
```bash
kit init          # Bootstraps .kit directory and AGENTS.md
```

### Memory Management
```bash
kit learn --tag invariant "Never use Redis"
kit recall "database connection"
```

### Governance & Runtime
```bash
kit watch         # Start real-time semantic event bus
kit preflight     # Run pre-commit checks (Git hook)
kit reflect       # Check current codebase for drift/violations
kit doctor        # Perform self-healing and deduplication
```

---
*For architectural details, see [ARCHITECTURE.md](ARCHITECTURE.md).*
