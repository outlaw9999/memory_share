# Brain State — Current Snapshot

**Last updated:** 2026-03-10
**System name:** Antigravity
**Brain version:** V2 (Phase 3 complete)
**Update channel:** Claude Cowork mode

---

## 1. System Overview

Antigravity is a long-term memory system for AI assistants. Its core problem: sending full conversation history to an LLM is expensive and noisy. The solution is a tiered memory model where only small, relevant snippets are injected into each prompt — not full logs.

The system is file-first: memory lives in Markdown files, indexed into a SQLite graph for semantic retrieval. This makes it inspectable, portable, and easy to version with Git.

---

## 2. Memory Layer Model

| Layer | Folder | Purpose | Default Privacy |
|-------|--------|---------|----------------|
| 1 | `layer1_stream/` | Append-only short-term logs and episode capture | `restricted` |
| 2a | `layer2_core/` | Shareable block-based operational memory | `shareable` |
| 2b | `layer2_private/` | Local-only personal memory | `private` |
| 3 | `layer3_index/` | Semantic + metadata retrieval index (SQLite) | local only |

Layer 3 queries exclude `private` by default.

---

## 3. How Retrieval Works

```
User query
    ▼
Vector search (top-K neurons by semantic similarity)
    ▼
Graph walk (synapse traversal to related concepts)
    ▼
Re-ranking (activation + access frequency + freshness)
    ▼
Context injection (~500 tokens into prompt)
```

A 1 GB memory archive costs ~1k tokens per query.

---

## 4. Brain V2 — Phase Status

### Phase 1 — Layer 2 Cleanup and Privacy Split ✅
### Phase 2 — Layer 3 Metadata and Retrieval Quality ✅
### Phase 3 — Background Consolidation ✅
### Phase 4 — Not yet defined

---

## 5. Runtime Status (verified 2026-03-10)

### Scripts runnable on Python 3.10+

| Script | Python | Status | Notes |
|--------|--------|--------|-------|
| `setup_workspace.py` | 3.10+ | ✅ Working | Creates dirs + SQLite schema |
| `layer3_metadata.py` | 3.10+ | ✅ Working | Stdlib only, no deps |
| `brain_maintenance.py` | 3.10+ | ✅ Working | Stdlib only, requires DB |
| `query_layer3.py` | 3.10+ | ✅ Working | Stdlib only, requires DB |
| `layer3_backfill.py` | 3.10+ | ✅ Working | Stdlib only, requires DB |
| `brain_sync_watcher.py` | **3.11+** | ⚠ Needs pip install | Requires `neural-memory`, `watchdog` |

### Bugs fixed (2026-03-10)
- `datetime.UTC` → `try/except` backport for Python 3.10 compat (all scripts)
- `layer3_metadata.py`: `utcfromtimestamp()` deprecated in 3.12 → `fromtimestamp(ts, tz=UTC)`
- `brain_sync_watcher.py`: broken `call_soon_threadsafe(create_task, ...)` → `run_coroutine_threadsafe(coro, loop)`

### One-time setup sequence
```bash
py -3 setup_workspace.py           # create dirs + DB schema
pip install -r requirements.txt    # Python 3.11+ venv for watcher only
py -3 brain/ops/brain_sync_watcher.py
```

---

## 6. Cross-Agent Usage (local)

The brain **can run cross-agent** on a single machine. Because all state lives in a shared SQLite file (`brain/layer3_index/neural_memory.db`) and Markdown files, any process that can read the filesystem can query or write to it.

### Current: subprocess call (works now)
Any agent can call `query_layer3.py` as a subprocess:
```python
import subprocess, json
result = subprocess.run(
    ["python3", "brain/ops/query_layer3.py", query, "--json"],
    capture_output=True, text=True, env={**os.environ, "ANTIGRAVITY_WORKSPACE_ROOT": root}
)
memories = json.loads(result.stdout)
```

### Better: MCP wrapper (Phase 4 candidate)
Wrapping `query_layer3.py` and `brain_sync_watcher.py` as MCP tools would let any MCP-compatible agent (Claude, Cursor, etc.) call the brain natively without subprocess boilerplate. This is the recommended path for Phase 4.

### Not supported yet
- Network/API access (no HTTP server)
- Multi-machine shared memory (no sync layer)
- Real-time push to remote agents

---

## 7. Key Operations Scripts

| Script | Purpose |
|--------|---------|
| `brain_sync_watcher.py` | Watches `layer1_stream/`, chunks and indexes into Layer 3 |
| `brain_maintenance.py` | Background consolidation — dedup, stale, promotion |
| `layer3_metadata.py` | Shared metadata utilities — path, chunk, privacy |
| `layer3_backfill.py` | Retrofits Phase 2 metadata onto existing SQLite records |
| `query_layer3.py` | CLI query with project/scope/privacy filters |
| `search.ps1` | Windows PowerShell text search (no SQLite needed) |

**Workspace root:** `ANTIGRAVITY_WORKSPACE_ROOT` env var, or 2 dirs above `brain/ops/`.

---

## 8. Metadata Schema (Layer 3)

Each indexed chunk carries:
```
metadata_version, project, project_slug, scope, privacy,
brain_name, source, source_path, source_file, source_layer,
source_kind, source_heading, source_heading_slug, source_date,
source_timestamp, chunk_index, chunk_count, chunk_chars,
content_hash, indexed_at
```

---

## 9. Cowork Integration (active)

Claude Cowork mode is the active brain sync operator:
- Trigger: "push brain update" in Cowork chat
- Reads public brain layer → synthesizes session doc → commits → pushes via SSH
- SSH key persisted in workspace `.ssh/` folder

---

## 10. Open Questions / Phase 4 Candidates

- MCP wrapper for `query_layer3` + `brain_sync_watcher` → native cross-agent
- HTTP API layer for multi-machine memory sharing
- Cross-session memory injection into Cowork context window
- `layer2_core` update workflow via Cowork agent
