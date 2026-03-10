# memory_share

Public-safe snapshot of **Antigravity** — a tiered long-term memory system for AI assistants.

This repo contains the architecture, operations scripts, and upgrade reports for `brain v2` after completing Phases 1–3. It is meant for architecture review and collaboration, not as a full production runtime.

---

## Why This Exists

Sending full conversation history to an LLM is expensive and noisy. Antigravity solves this with a **tiered memory model**: memory lives in Markdown files, indexed into a SQLite graph for semantic retrieval. Each query injects only the most relevant ~500-token snippet — not the entire archive.

> A 1 GB memory file can serve a query for ~1k tokens after years of history.

---

## Memory Layer Model

| Layer | Folder | Purpose | Default Privacy |
|-------|--------|---------|----------------|
| 1 | `layer1_stream/` | Append-only short-term logs and episode capture | `restricted` |
| 2a | `layer2_core/` | Shareable block-based operational memory | `shareable` |
| 2b | `layer2_private/` | Local-only personal memory | `private` |
| 3 | `layer3_index/` | Semantic + metadata retrieval index (SQLite) | local only |

Layer 3 queries exclude `private` by default. Only `shareable` and `restricted` memories participate in standard retrieval.

---

## How Retrieval Works

```
User query
    │
    ▼
Vector search (sentence-transformers / OpenAI-small)
    │  Find top-K neurons semantically similar to the query
    ▼
Graph walk (Synapse traversal)
    │  Follow edges to related concepts
    ▼
Re-ranking
    │  Sort by activation level + access frequency + freshness
    ▼
Context injection (~500 tokens)
    │  Stitch top 3–5 neuron texts into the prompt
    ▼
LLM
```

---

## Brain V2 — Phase Status

### Phase 1 — Layer 2 Cleanup and Privacy Split ✅
Split `layer2_private/` from `layer2_core/`. All memory files now carry `scope`, `privacy`, `owner`, and `updated_at` frontmatter. Personal memory no longer lives inside shareable files.

### Phase 2 — Layer 3 Metadata and Retrieval Quality ✅
Every indexed chunk carries stable metadata including `project`, `scope`, `privacy`, `source_layer`, `source_heading`, `content_hash`, and `indexed_at`. Retrieval can be filtered by any of these. Backfill tooling retrofits existing SQLite records.

### Phase 3 — Background Consolidation ✅
A maintenance job classifies each anchor memory as `promotion_candidate`, `duplicate`, `stale_candidate`, or assigns a `hot/warm/cold` bucket. Non-destructive: no records are deleted. Output is written to `layer2_core/maintenance_digest.md`.

### Phase 4 — Not yet defined
Open question: cross-session memory injection into Cowork context.

---

## Repository Structure

```
memory_share/
├── README.md
├── SHARE_NOTES.md
├── brain/
│   ├── exports/
│   │   └── neural_memory_architecture.md   # Architecture overview and code walkthrough
│   └── ops/
│       ├── brain_sync_watcher.py           # Watches layer1_stream, chunks + indexes into Layer 3
│       ├── brain_maintenance.py            # Background consolidation: dedup, stale, promotion
│       ├── layer3_metadata.py              # Shared metadata utilities for all scripts
│       ├── layer3_backfill.py              # Retrofits Phase 2 metadata onto existing records
│       ├── query_layer3.py                 # CLI query tool with project/scope/privacy filters
│       └── search.ps1                      # Windows PowerShell search wrapper
└── reports/
    ├── brain_v2_update_roadmap.md          # Phase plan and design decisions
    ├── layer3_metadata_schema.md           # Full metadata field reference
    ├── background_consolidation_policy.md  # Consolidation rules and thresholds
    ├── brain_state_current.md             # Full system state snapshot (latest)
    └── cowork_integration_session.md      # Cowork agent setup and sync workflow
```

---

## Operations Scripts

### `brain_sync_watcher.py`
Monitors `layer1_stream/` for new or updated Markdown files. On change: chunks the content semantically, encodes each chunk into a neuron via `neural_memory`, and saves to the SQLite Layer 3 index. Uses `layer3_metadata.py` to build rich metadata per chunk.

### `brain_maintenance.py`
Background consolidation job. Reads all anchor neurons in Layer 3, applies classification rules, and writes a digest to `layer2_core/maintenance_digest.md`. Configurable thresholds:

| Threshold | Default |
|-----------|---------|
| `stale_days` | 30 |
| `weak_activation` | 0.1 |
| `weak_access_frequency` | 1 |
| `promotion_limit` | 8 |

### `layer3_metadata.py`
Shared utilities used by all other scripts: workspace root resolution, path slugification, timestamp inference from filenames, chunk metadata builder, and privacy defaults by source layer.

### `layer3_backfill.py`
One-time or re-runnable migration tool. Reads existing Layer 3 SQLite records and retrofits Phase 2 metadata fields. Supports `--dry-run` for safe inspection before writing.

### `query_layer3.py`
CLI interface for structured Layer 3 queries.

```bash
py -3 query_layer3.py "API login bug" --project my_project --scope workspace
```

Supports filters: `--brain`, `--project`, `--scope`, `--privacy`.

### `search.ps1`
PowerShell wrapper for running searches on Windows.

---

## Layer 3 Metadata Schema

Each indexed chunk carries:

```
metadata_version    project             project_slug
scope               privacy             brain_name
source              source_path         source_file
source_layer        source_kind         source_heading
source_heading_slug source_date         source_timestamp
chunk_index         chunk_count         chunk_chars
content_hash        indexed_at
```

Full field descriptions: [`reports/layer3_metadata_schema.md`](reports/layer3_metadata_schema.md)

---

## Cowork Integration

Claude Cowork mode acts as the active brain sync operator for this repo:

1. Trigger: say "push brain update" in Cowork chat
2. Agent reads the public brain layer from this repo
3. Agent synthesizes a session update doc (no personal data)
4. Agent commits and pushes via SSH — no token needed

SSH authentication uses an ED25519 key persisted in the workspace `.ssh/` folder.

---

## Getting Started (local review)

```bash
# Verify all scripts parse cleanly
py -3 -m py_compile brain/ops/*.py

# Query Layer 3 (requires local SQLite db at brain/layer3_index/neural_memory.db)
py -3 brain/ops/query_layer3.py "your search query"

# Run maintenance (dry run)
py -3 brain/ops/brain_maintenance.py --dry-run
```

Set `ANTIGRAVITY_WORKSPACE_ROOT` to point scripts at your local workspace root if running outside the default directory layout.

---

## What Is Intentionally Missing

This repo is a **public-safe snapshot**, not a full runtime. It excludes:

- personal memory (`layer2_private/`)
- live stream logs (`layer1_stream/`)
- SQLite databases (`layer3_index/neural_memory.db`)
- runtime state (`.sync_state.json`, backups)
- machine-specific paths and environment configs

---

## Privacy

No personal data, credentials, private memory, or runtime state is tracked in this repository. All commits use a generic `Cowork Agent` identity.
