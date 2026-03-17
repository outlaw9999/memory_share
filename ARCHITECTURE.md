# .kit — Agent Memory Share Bus (AMSB)

## Architecture Overview
`.kit` is a protocol-first cognitive infrastructure for AI agents. It provides a shared memory space (Cognitive Bus) that is deterministic, event-driven, and governed by architectural discipline.

## Core Philosophical Pillars
1. **Unix Primitive**: Small at the core, open for the ecosystem. Works via CLI, JSON, and Pipes.
2. **Deterministic Memory**: `materialized_score` ensures every agent and human sees the same cognitive ranking.
3. **Event-Driven**: Agents react to changes via `kit watch` polling the SQLite WAL version.
4. **Cognitive Governance**: `kit preflight` prevents architectural entropy before it hits the repository history.

## Technical Stack
- **Storage**: SQLite + FTS5 (external content) + WAL mode.
- **Cognition**: Quad-store (Nodes, Edges, Observations, Commits).
- **Versioning**: Branch-based versioning with atomic increment.

## Key Epochs
- **Epoch 12**: AMSB - Multi-agent shared memory + Materialized scores.
- **Epoch 13**: Governance - `kit preflight` discipline layer.

## Command Interface
- `kit learn`: Append new observations.
- `kit recall`: Context-anchored retrieval.
- `kit watch`: Real-time semantic event stream.
- `kit preflight`: Pre-commit architectural gatekeeper.
