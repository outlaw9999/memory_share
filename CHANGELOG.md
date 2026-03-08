# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-08

### Added
- **Semantic Symbol Identity**: Deterministic `file::scope::name` formula for precise symbol reference
- **Identity-Based Call Graph**: Migration from name-based to ID-based edges prevents symbol collisions
- **Transactional Schema Migration**: Atomic, reversible Phase 10 migration with automatic rollback
- **Portable `.kit` Artifacts**: Shareable semantic code graph databases queryable without external services
- **WAL Mode Support**: SQLite Write-Ahead Logging for concurrent reads from multiple agents
- **UNIQUE Constraints**: Prevents duplicate edges in call graph during incremental indexing

### Fixed
- Symbol collision resolution for multi-file repositories
- Concurrent read-safety via WAL mode
- Call graph integrity via UNIQUE constraints

### Architecture
- **Phase 1-10 Roadmap Completed**: Architecture is now frozen for API stability
- **5-Layer Stack**: Semantic → Graph Reasoning → Context Retrieval → Storage → Artifacts
- **Local-First Design**: Zero infrastructure, offline-first, single-file distribution

---

## What is `.kit`?

A **local-first semantic code graph engine** that compiles your repository into a portable, queryable artifact. No cloud services. No heavy dependencies. Just SQLite + FTS5.

### The Problem It Solves

* **Today's reality**: AI coding assistants rely on slow cloud parsing, expensive graph databases, or blind text search
* **Our solution**: Pre-compiled semantic graph that any agent can query in < 10ms

---

## What's in v1.0.0?

### Core Features

#### 1. **Symbol Search** (Phase 8)
```bash
kit symbol "parse"
```
Ranked, full-text search for symbols with deterministic ranking.

#### 2. **Code Context** (Phase 8)
```bash
kit context "Parser.parse"
```
Get definition, callers, callees, and code snippet all at once.

#### 3. **Forward Exploration** (Phase 9)
```bash
kit related "parse"
```
Find similar symbols, direct callers/callees, and module peers.

#### 4. **Reverse Graph Traversal** (Phase 9)
```bash
kit impact "parse"
```
Analyze blast radius - see what breaks if you change this symbol. Cycle-safe.

#### 5. **Semantic Identity** (Phase 10)
```
file::scope::name
```
Each symbol has a deterministic, language-independent identity. No more "which `parse()` do you mean?"

---

## Architecture Highlights

### Layered Design
```
Semantic Layer
    ↓ (symbol_id → file::scope::name)
Graph Reasoning Layer
    ↓ (related, impact)
Context Retrieval Layer
    ↓ (symbol, snippet, context)
Storage Layer
    ↓ (SQLite + FTS5 + WAL)
```

### Portable Artifacts

The main **product** is `.kit` databases:
```
memory_share.kit
├── .antigravity/atlas/atlas.db
│   ├── symbols (identity-based, deduplicated)
│   ├── calls (identity-based edges)
│   └── symbol_fts (full-text search index)
└── code/ (repository snapshot)
```

Once generated, a `.kit` file can be:
- Shared with teammates
- Passed to LLM agents
- Queried in any CI/CD pipeline
- Archived for historical analysis

---

## What Changed in Phase 10?

### From Name-Based to Identity-Based

**Before (Phase 9)**:
```python
parser_a.parse()  # calls which parse()?
parser_b.parse()  # collision risk
```

**After (Phase 10)**:
```
parser_a.py::module::parse  # ✓ Unique
parser_b.py::module::parse  # ✓ Unique
```

### Schema Migration

Automatic, transactional migration:
```sql
-- Old schema (name-based)
calls(caller TEXT, callee TEXT, file TEXT, line INTEGER)

-- New schema (identity-based)
calls(caller_id TEXT, callee_id TEXT, file TEXT, line INTEGER)
```

Run once with `python run_migration_phase10.py .antigravity/atlas/atlas.db`

---

## Performance

Target latencies achieved on local repositories:

| Operation | Time |
|-----------|------|
| `kit symbol "foo"` | < 10 ms |
| `kit context "Bar"` | < 20 ms |
| `kit related "baz"` | < 20 ms |
| `kit impact "qux"` | < 30 ms |

Measured on repository with ~10K symbols.

---

## Concurrency Safety

✅ **Multiple reads**: Safe (SQLite WAL mode)
- Readers don't block each other
- Queries from multiple LLM agents in parallel

⚠️ **Writing**: Single-writer model
- Only one indexer process can update `.kit` at a time
- Use journal tailer for incremental updates

---

## Reliability

### Test Coverage
- **46 tests** covering all major code paths
- **3 migration tests** verify atomic, disaster-safe schema upgrade
- **2 identity tests** verify deterministic symbol deduplication
- **9 contract tests** lock down frozen API (Phase 8)

### Backward Compatibility
- All Phase 8 CLI contracts frozen
- Phase 9, 10 additions are non-breaking
- WAL mode enabled for concurrent reads without schema changes

---

## Known Limitations (v1.0)

1. **Language Support**: Python indexer only
   - Phase 11: TypeScript, Java, Go adapters

2. **Repository Size**: Tested up to 100K symbols
   - Larger repos may need optimization

3. **Real-Time Updates**: Incremental indexing is sequential
   - For live editing: use journal tailer between commits

4. **Compression**: No built-in compression
   - `.kit` files are uncompressed SQLite
   - Can be gzipped for distribution

---

## Getting Started

### Quick Start
```bash
# Clone
git clone https://github.com/outlaw9999/memory_share.git
cd memory_share

# Install dependencies
pip install -r requirements.txt

# Build index for current repo
python kit.py symbol "your_symbol_here"

# Explore your code
python kit.py context "MyClass"      # Full context
python kit.py related "myfunction"   # Nearby symbols
python kit.py impact "critical_fn"   # What breaks if I change it?
```

### For Agents
```python
from kit_adapters import AtlasAdapter
from pathlib import Path

atlas = AtlasAdapter(Path('.'))

# Search
results = atlas.search("parse", limit=10)

# Get context for a symbol
context = atlas.get_unified_context("Parser.parse")

# Analyze impact
impact = atlas.get_impact_analysis("Parser.parse", depth=3)
```

---

## Road Map (Beyond v1.0)

### Phase 11: Multi-Language Support
- TypeScript/JavaScript adapter
- Java adapter
- Go adapter
- Language-specific scope analysis

### Phase 12: Distributed Graphs
- Multiple `.kit` databases working together
- Cross-repository navigation
- Dependency graph assembly

### Phase 13: Real-Time Indexing
- Live sync with editor changes
- Sub-second index updates
- Agent-friendly change events

---

## Contributing

This is the **architecture freeze** for the core engine (Phase 1-10). Extension work (Phase 11+) is open for contribution.

Currently seeking:
- [ ] Language adapter implementations
- [ ] Performance optimizations for large repos
- [ ] Integration with popular LLM frameworks (LangChain, etc.)

---

## License

[Your license here - likely MIT or Apache 2.0]

---

## Credits

Designed for AI agents and developers who need to reason about code structure, not just read text.

---

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: [contact email]

---

**Happy graphing! 🧠🌐🚀**
