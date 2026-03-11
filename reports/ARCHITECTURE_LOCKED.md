# ARCHITECTURE_LOCKED.md
[version: v1.1.0]

This manifest serves as the absolute "Constitution" for the `.kit` intelligent engine. Any AI Agent or Developer working on this codebase MUST adhere to these constraints and performance budgets. If any modifications cause these constraints or budgets to be violated, the PR must be REJECTED.

---

## 🏗️ 1. SYSTEM INVARIANTS (The Golden Rules)

### Directory Governance (Clean Architecture)
- `kit/cli/`: **Orchestration Layer**. Strictly parses arguments and delegates. **NEVER** import anything from `kit/core/` directly. 
- `kit/services/`: **Service Layer**. Coordinates core modules (Graph, Memory, Adapters). The **ONLY** layer allowed to import `kit/core/`.
- `kit/core/`: **Core Domain Layer**. Abstract Data Structures, Graph Algorithms, SQLite interactions, and Parsers.

### Sacred Memory (Cognitive Continuity)
- The directory `brain/` holds memory chunks and user-facing artifacts (`ARCHITECTURE_LOCKED.md`, `SHARE_NOTES.md`).
- **RULE**: NEVER auto-merge, condense, or reorganize `brain/` files. The raw memory structure is sacred for Cognitive Bridge retrieval.
- **RULE**: Temporary "Archives" (`_archived/`, `old_code/`) are strictly forbidden to prevent LLM Hallucinations.

### Subprocess Rules (Agent Safety)
- ALL subprocess calls (like `gemini-cli`, external tools) executed via adapters MUST implement a strict `timeout` (e.g., `timeout=10`).
- Hanging quietly is a fatal error. Fail fast.

---

## 📝 2. ENGINE CONTRACTS

### The Dual Graph Contract
The system operates on a Unified Cognitive Bridge combining:
1. **The Code Graph (`atlas.db`)**: Absolute truth. Fast SQL relations.
2. **The Memory Graph (`neural_memory.db`)**: Contextual truth. LLM embeddings and structural insights.

### SQL Traversal (The "Stones" Rule)
- All complex querying (hotspots, coupling entropy, graph cycles) must be offloaded to raw SQL (`.antigravity/queries/stones/`). 
- **NO PYTHON RANGING OR MULTIPLE DB CALLS** for topological analytics.

### Infinite Traversal Protection (The BFS Rule)
- Any internal Graph Traversal in Python (e.g. `graph_slice_engine.py`) MUST implement a strict `visited = set()` check and depth limit (`max_depth`). A cycle without `visited` is an immediate deadlock.

### Immutable AI Capabilities
- The file `.antigravity/stones.yaml` is the **Single Source of Truth** for LLM abilities. An Agent cannot assume or hallucinate a tool not explicitly bounded in the `stones.yaml` contract.

---

## ⚡ 3. PERFORMANCE BUDGETS

These time limits are non-negotiable. Exceeding them indicates an I/O regression (like using `rglob`), an unchecked cycle, or a missing DB Index.

- **Incremental File Indexing**: `< 50ms` per file.
- **Full Codebase Index Scan (Pruned)**: `< 2s` (Must prune `.venv`, `node_modules`, `build`).
- **SQL Stone Execution**: `< 200ms`.
- **Graph Slice Query (BFS + Ranking)**: `< 400ms`.
- **`kit doctor` Orchestrator Report**: `< 2s` overall.

---

## 📊 DATA FLOW ARCHITECTURE

```mermaid
graph TD
    CLI[CLI Layer (main.py)] -->|Arguments| SRV[Service Layer]
    
    SRV -->|Fetch Code Context| AST[AST Scanner / Indexer]
    SRV -->|Run Diagnostics| ST[SQL Stones (.sql)]
    SRV -->|Extract Semantics| GSE[Graph Slice Engine]
    SRV -->|Query Memory| MEM[Memory Adapter]

    AST -->|Write Truth| DB_A[(atlas.db)]
    ST -->|Read Fast| DB_A
    GSE -->|Bounded Traverse| DB_A
    
    MEM <-->|Fuse Context| DB_M[(neural_memory.db)]
    
    SRV -->|Unified Insight| ROUTER[Cognitive Router]
    ROUTER -->|JSON / Explain| CLI
```

**Status:** FROZEN (v1.1.0)
