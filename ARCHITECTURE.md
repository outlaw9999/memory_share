# .kit Technical Architecture (SAM Epoch)

This document defines the low-level technical specifications of the .kit Memory Engine.

## 📊 The Quad-Store Schema
.kit operates on four primary logical pillars:

1. **Nodes (entities)**: Identifiers and classification of entities.
2. **Observations (facts)**: Atomic knowledge and episodic records.
3. **Edges (relations)**: Temporal links between entities.
4. **Keyword Index (facts_fts)**: High-speed FTS5 search engine.

### Fact Ledger Schema
```sql
CREATE TABLE facts (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    supersedes_id INTEGER, -- Lineage link
    is_active BOOLEAN DEFAULT 1,
    metadata TEXT DEFAULT '{}', -- JSON Escape Hatch
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🔍 SQLite Search Engine (FTS5 Core)
Instead of heavy Vector Search, .kit uses **FTS5 External Content** for lightning-fast keyword lookup.
- **Porter Tokenizer**: Automatically stems words (e.g., `connecting` -> `connect`).
- **Zero Duplication**: The FTS index only stores pointers to raw content.
- **Sub-50ms Latency**: Near-instant retrieval even with large datasets.

## 🧠 Cognitive Ranking Algorithm
.kit uses a natural decay algorithm to preserve long-term knowledge without it being "washed away" by time.

$$Score = Importance \times \log_{10}(AccessCount + 2) \times \frac{1}{1 + (DaysOld / 30)}$$

| Factor | Role | Description |
| :--- | :--- | :--- |
| **Importance** | Semantic Weight | Intrinsic value (0.1 - 1.0). |
| **Frequency** | Reinforcement | Boosts score based on usage (Log-scale). |
| **Recency** | Half-life Decay | Natural decay over time (Default: 30 days). |

## ⏳ Temporal Graph Memory
- **Snapshot Query**: Retrieve knowledge state at any point in time using `--at`.
- **Relationship Lineage**: Links carry `created_at` and `superseded_at` markers for audit trails and rollback.

## 🛠️ Public API (`kit/api.py`)
- `init_kernel(db_path)`: Initialize engine.
- `learn(uid, kind, content, replaces_id=None)`: Ingest memory.
- `recall(entities, limit)`: Contextual ranked retrieval.
- `export_prompt(entities, limit)`: Generate AI-ready context.
