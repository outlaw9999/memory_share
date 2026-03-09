# `.kit` — Local Semantic Code Graph for Agents

[![Release: v1.0.0](https://img.shields.io/badge/release-v1.0.0-green?logo=github)](https://github.com/outlaw9999/memory_share/releases/tag/v1.0.0)
[![Status: Stable](https://img.shields.io/badge/status-stable-green)](docs/ARCHITECTURE_FREEZE.md)
[![Architecture: Frozen](https://img.shields.io/badge/architecture-frozen-blue)](docs/ARCHITECTURE_FREEZE.md)

A lightweight, offline-first code intelligence substrate for AI agents and developer tools. Compiles any repository into a portable `.kit` artifact that answers precise code questions in **< 30ms**, all local, zero infrastructure.

**Status**: v1.0.0 is PRODUCTION READY. Architecture frozen for backward compatibility. See [CHANGELOG.md](CHANGELOG.md) and [V1_RELEASE_NOTES.md](V1_RELEASE_NOTES.md) for details.

## Why `.kit`?

Instead of:
- ❌ Paying for cloud AST parsing services
- ❌ Running heavy graph databases
- ❌ Blind text search that misses context

You get:
- ✅ Deterministic symbol identity (`file::scope::name`)
- ✅ Semantic graph reasoning (forward & reverse traversal)
- ✅ Sub-30ms queries on repositories with 100K+ symbols
- ✅ Portable, shareable `.kit` artifacts
- ✅ Built for agents that need to reason about code

## Quick Start

```bash
# Install
git clone https://github.com/outlaw9999/memory_share
pip install -r requirements.txt

# Index your repository
python kit.py symbol "MyClass"         # Search by symbol

# Explore relationships
python kit.py context "Parser.parse"   # Full context
python kit.py related "tokenize"       # Nearby symbols
python kit.py impact "critical_fn"     # Reverse: what breaks?
```

## Core Capabilities

| Command | Purpose | Status |
|---------|---------|--------|
| `kit symbol <query>` | Search symbols by name | ✅ Phase 8 |
| `kit context <symbol>` | Get definition + callers + callees | ✅ Phase 8 |
| `kit snippet <file>:<line>` | Read code around a line | ✅ Phase 8 |
| `kit related <symbol>` | Explore nearby code | ✅ Phase 9 |
| `kit impact <symbol>` | Reverse traversal (blast radius) | ✅ Phase 9 |

## Architecture: Phase 1-10 Complete

`.kit` evolved through 10 phases:

```
Phase 1-5:   Local code indexing (SQLite + FTS5)
Phase 6-7:   Indexing pipeline (incremental updates)
Phase 8:     Context engine (frozen API for stability)
Phase 9:     Graph exploration (forward & reverse reasoning)
Phase 10:    Semantic identity (precise symbol location)
```

### Final Stack

```
Symbol Identity Layer (file::scope::name)
       ↓
Graph Reasoning (related, impact)
       ↓
Context Retrieval (symbol, snippet, context)
       ↓
Storage (SQLite + FTS5 + WAL mode)
```

The **product** is portable `.kit` artifacts that agents can query without external services.

## Why This Matters

Modern AI coding assistants need to **reason** about code structure, not just read text.

- **Precise**: No ambiguity about which symbol is being referenced
- **Fast**: < 30ms queries, interactive agent loops
- **Offline**: No cloud dependency, full control over data
- **Portable**: Pass `.kit` files between tools and teams
- **Deterministic**: Same results across all runs and machines

## Test Coverage

✅ **46/46 tests passing**
- Storage & indexing (Phase 6-7)
- Context retrieval (Phase 8)
- Graph reasoning (Phase 9)
- Symbol identity & migration (Phase 10)

See [ARCHITECTURE.md](ARCHITECTURE.md) for full design documentation.

## For AI Agents

```python
from kit_adapters import AtlasAdapter
from pathlib import Path

kit = AtlasAdapter(Path('.'))

# Search for symbols
results = kit.search("parse", limit=10)

# Get unified context
context = kit.get_unified_context("Parser.parse")

# Analyze impact (reverse call graph)
impact = kit.get_impact_analysis("critical_fn", depth=3)
```

## Known Limitations (v1.0)

- **Single Language**: Python indexer (Phase 11+ adds TypeScript, Java, Go)
- **Single-Writer**: Serialize indexing (but multi-reader safe via WAL)
- **Repository Size**: Tested up to 100K symbols
- **No Compression**: Uncompressed SQLite (can gzip for distribution)

All limitations are documented with mitigation strategies.

## Road Map

### Phase 11: Multi-Language Adapters
- [ ] TypeScript/JavaScript indexer
- [ ] Java indexer
- [ ] Go indexer

### Phase 12: Distributed Graphs
- [ ] Merge multiple `.kit` databases
- [ ] Cross-repository navigation
- [ ] Dependency graph assembly

### Phase 13: Real-Time Indexing
- [ ] Live sync with editor changes
- [ ] Sub-second index updates
- [ ] Event streaming for agents

## Project Structure

```
memory_share/
├── kit.py                    # CLI entry point
├── kit_adapters.py           # Atlas + Brain adapters
├── plugins/
│   ├── atlas_indexer/        # Graph storage & indexing
│   └── journal_tailer/       # WAL event processor
├── tests/                    # Test suite (46 tests)
├── docs/                     # Documentation
├── README.md
├── ARCHITECTURE.md
└── requirements.txt
```

## Contributing

This is an **architecture freeze** for Phase 1-10 (core engine).

We're actively seeking contributions for:
- Language adapters (Phase 11)
- Distributed graph support (Phase 12)
- Integration with LLM frameworks

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Full 10-phase design walkthrough
- **[RELEASE_NOTES.md](docs/RELEASE_NOTES.md)** — v1.0.0 changelog and features

## License

[License TBD - MIT or Apache 2.0]

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Built for tools and agents that need to reason about code structure, not just read text.**

Join the community turning every repository into an explorable knowledge graph. 🧠🌐✨

```text
kit symbol <symbol>
kit related <symbol>
```

Planned:

```text
kit impact <symbol>
```

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
kit related <symbol> --json
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

`kit related` is the exploration query for agent workflows. It aggregates:

- similar symbol names from the local FTS index
- direct callers and callees from the call graph
- peer symbols from the same file/module

Planned next step:

- `kit impact <symbol>` for reverse call-graph traversal and blast-radius analysis

## Caveats

- Snapshot assumption: `kit snippet` reads directly from the filesystem. Results may diverge if indexing has not caught up with recent edits.
