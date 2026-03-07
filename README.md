# Memory Share

This repository is a public-safe, shareable version of the Antigravity memory system after Phase 1 to Phase 3 of the `brain v2` upgrade.

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
