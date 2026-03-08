# Memory Share

This repository is a public-safe, shareable version of the Antigravity memory system after Phase 1 to Phase 3 of the `brain v2` upgrade.

See [SHARE_NOTES.md](SHARE_NOTES.md) for a short collaborator-oriented note on what this repo is, what is intentionally missing, and how to review it.

It includes:

- a high-level explanation of how `brain` and `memory` work
- the watcher that indexes Markdown memory into Layer 3
- metadata-aware Layer 3 query and backfill tools
- a background consolidation job for duplicate, stale, and promotion review
- architecture and rollout reports

It excludes:

- personal notes
- private Layer 2 memory
- daily live logs
- local SQLite databases and backups
- runtime state
- unrelated project history

## Memory Model

The system uses four working layers:

| Layer | Purpose |
|------|---------|
| `layer1_stream` | recent working notes and short-term logs |
| `layer2_core` | shareable operational memory |
| `layer2_private` | local-only personal memory |
| `layer3_index` | semantic retrieval index stored locally in SQLite |

## What This Version Demonstrates

### Phase 1

- shareable vs private memory split
- block-based Layer 2 organization

### Phase 2

- metadata-aware Layer 3 indexing
- query by `project`, `scope`, `privacy`, and provenance
- backfill for existing SQLite records

### Phase 3

- background consolidation
- duplicate and stale classification
- promotion candidate surfacing
- maintenance digest generation

## Included Files

### Operations

- `brain/ops/brain_sync_watcher.py`
- `brain/ops/brain_maintenance.py`
- `brain/ops/search.ps1`
- `brain/ops/layer3_metadata.py`
- `brain/ops/layer3_backfill.py`
- `brain/ops/query_layer3.py`

### References

- `brain/exports/neural_memory_architecture.md`
- `reports/brain_v2_update_roadmap.md`
- `reports/layer3_metadata_schema.md`
- `reports/background_consolidation_policy.md`

## Privacy

This repository is intentionally safe to share. It does not include any live Layer 2 memory files, private user data, stream logs, SQLite indexes, or runtime state.

## Query Interface

`memory_share.kit` exposes a small CLI query surface designed for agents and automation.

Primary commands:

```bash
kit symbol <query> --json
kit callers <symbol> --json
kit snippet <path>:<line> --json
kit context <symbol> --json
```

Design goals:

- CLI-first: usable from any environment without IDE plugins
- JSON-first: stable machine-readable outputs for agents and automation
- filesystem-first: no daemon or server required

The CLI aggregates information from two internal systems:

```text
kit
 |
 +- Atlas (plugins/atlas_indexer/)
 |   code graph + symbol index
 |
 +- Brain (brain/)
     cognitive memory + documentation metadata
```

All commands return a stable JSON envelope so tools and agents can treat `kit` as the official query API.

`kit context` is the highest-level query for agent workflows. It aggregates:

- the best matching code definition
- caller and callee relationships
- a local source snippet around the definition
- related Brain documentation hits
- simple metrics such as caller/callee/doc counts

## Caveats

- Snapshot assumption: `kit snippet` reads directly from the filesystem. Results may diverge if indexing has not caught up with recent edits.
