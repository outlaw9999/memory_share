# Memory Share

This repository is a minimal, shareable version of the Antigravity memory system.

It includes:

- a high-level explanation of how `brain` and `memory` work
- the core watcher and maintenance scripts
- a sample architecture document for semantic memory

It excludes:

- personal notes
- daily logs
- local databases
- runtime state
- unrelated project history

## Memory Model

The system uses three layers:

| Layer | Purpose |
|------|---------|
| `layer1_stream` | recent working notes and short-term logs |
| `layer2_core` | durable operational memory such as principles and decisions |
| `layer3_index` | semantic retrieval index stored locally in SQLite |

## How It Works

1. Session notes are written to Markdown files.
2. `brain_sync_watcher.py` monitors new or updated notes.
3. New text is chunked semantically.
4. Chunks are encoded into the `neural_memory` index.
5. Later queries retrieve only relevant snippets instead of full history.

This reduces token usage and keeps long-term memory outside the chat window.

## Included Files

- `brain/ops/brain_sync_watcher.py`
- `brain/ops/brain_maintenance.py`
- `brain/ops/search.ps1`
- `brain/exports/neural_memory_architecture.md`

## Privacy

This repo is intentionally safe to share. It does not include any personal memory files or local runtime artifacts.
