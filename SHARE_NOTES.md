# Share Notes

This repository is a trimmed, public-safe snapshot of the Antigravity memory system after Phase 1 to Phase 3 of the `brain v2` upgrade.

It is meant for architecture review and discussion, not as a full production runtime.

## What To Look At First

1. `README.md` for the high-level memory model.
2. `brain/exports/neural_memory_architecture.md` for the original architecture overview.
3. `brain/ops/brain_sync_watcher.py` for ingestion into Layer 3.
4. `brain/ops/query_layer3.py` and `brain/ops/layer3_metadata.py` for metadata-aware retrieval.
5. `brain/ops/brain_maintenance.py` for background consolidation.
6. `reports/` for the upgrade roadmap and policy decisions.

## What Is Intentionally Missing

- personal memory
- private Layer 2 files
- live stream logs
- local SQLite databases
- runtime state and machine-specific paths
- unrelated project history

## What Changed In Phase 1 To 3

- Phase 1: split shareable and private memory, and reorganized Layer 2 into clearer blocks
- Phase 2: added Layer 3 metadata, filters, and backfill tooling
- Phase 3: added background consolidation for duplicate, stale, and promotion review

## Safe Ways To Review

- Read the architecture and policy docs in `reports/`
- Inspect the Python scripts in `brain/ops/`
- Run `py -3 -m py_compile brain/ops/*.py` to check syntax

The repository is intentionally incomplete as an execution environment. It shows the memory model, not the full AI-OS kernel.
