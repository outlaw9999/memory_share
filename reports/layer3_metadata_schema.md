# Layer 3 Metadata Schema

## Goal

Phase 2 standardizes metadata on Layer 3 anchor memories so retrieval can filter by project, scope, privacy, and provenance.

## Record Shape

Each anchor neuron should carry these metadata fields:

| Field | Purpose |
|------|---------|
| `metadata_version` | schema version marker |
| `project` | human-readable project name |
| `project_slug` | normalized project identifier |
| `scope` | `workspace` or `project` |
| `privacy` | `shareable`, `restricted`, or `private` |
| `brain_name` | owning NeuralMemory brain |
| `source` | absolute source path for compatibility |
| `source_path` | workspace-relative source path |
| `source_file` | source filename |
| `source_layer` | `layer1_stream`, `layer2_core`, `layer2_private`, or `unknown` |
| `source_kind` | `daily_log`, `project_stream`, `core_memory`, `private_memory`, or `unknown` |
| `source_heading` | primary markdown heading for the chunk |
| `source_heading_slug` | normalized heading id |
| `source_date` | date inferred from filename when available |
| `source_timestamp` | timestamp inferred from file mtime |
| `chunk_index` | chunk position within the ingested file delta |
| `chunk_count` | chunk count for the ingested file delta |
| `chunk_chars` | chunk size in characters |
| `content_hash` | short hash of the chunk text |
| `indexed_at` | timestamp of indexing |

## Privacy Defaults

- `layer1_stream` -> `restricted`
- `layer2_core` -> `shareable`
- `layer2_private` -> `private`

## Retrieval Rules

- Default Layer 3 queries should exclude `private`.
- Private results should only appear when explicitly requested.
- Shareable and restricted memories may both participate in local retrieval.

## Ranking Signals

Phase 2 ranking uses:

1. FTS text score
2. access frequency
3. activation level
4. small freshness bonus
