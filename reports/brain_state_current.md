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

| Layer | Name | Purpose | Privacy |
|-------|------|---------|---------|
| Layer 1 | `layer1_stream` | Append-only short-term logs and episode capture | restricted |
| Layer 2a | `layer2_core` | Shareable block-based operational memory | shareable |
| Layer 2b | `layer2_private` | Local-only personal memory | private |
| Layer 3 | `layer3_index` | Semantic + metadata retrieval index (SQLite) | local only |

**Key rule:** Layer 3 queries exclude `private` by default. Only `shareable` and `restricted` memories participate in standard retrieval.

---

## 3. How Retrieval Works

When the bot needs context for a query:

1. **Vector search** — find the top-K neurons semantically similar to the query
2. **Graph walk** — traverse synapse edges from matched neurons to related concepts
3. **Re-ranking** — sort by activation level, access frequency, freshness
4. **Context injection** — stitch top 3–5 neuron texts into the prompt (~500 tokens)

This means a 1GB memory archive costs only ~1k tokens per query.

---

## 4. Brain V2 Upgrade — Phase Status

### Phase 1 — Layer 2 Cleanup and Privacy Split ✅
- Created `layer2_private/` to isolate personal memory
- Split all core notes into block files with frontmatter
- Added `scope`, `privacy`, `owner`, `updated_at` fields
- All core memory files now have a defined scope

### Phase 2 — Layer 3 Metadata and Retrieval Quality ✅
- Every indexed record carries stable metadata (see `layer3_metadata_schema.md`)
- Retrieval can be filtered by `project`, `scope`, `privacy`, `source_layer`
- `layer3_backfill.py` retrofits metadata onto existing SQLite records
- `query_layer3.py` supports structured queries with multiple filter flags

### Phase 3 — Background Consolidation ✅
- `brain_maintenance.py` classifies each anchor memory into:
  - `promotion_candidate` — important stream note ready for Layer 2
  - `duplicate` — same content hash within a brain
  - `stale_candidate` — old, low-activation, low-access
  - maintenance bucket: `hot`, `warm`, or `cold`
- Non-destructive: no neurons, fibers, or typed memories are deleted in Phase 3
- Output: `layer2_core/maintenance_digest.md`

### Phase 4 — Not yet defined
Open question: cross-session memory injection into Cowork context.

---

## 5. Key Operations Scripts

| Script | Purpose |
|--------|---------|
| `brain_sync_watcher.py` | Watches `layer1_stream/`, chunks and indexes new content into Layer 3 via `neural_memory` library |
| `brain_maintenance.py` | Background consolidation job — classifies duplicates, stale, and promotion candidates |
| `layer3_metadata.py` | Shared metadata utilities — path resolution, slugify, timestamp inference, chunk metadata builder |
| `layer3_backfill.py` | Retrofits Phase 2 metadata onto existing Layer 3 SQLite records |
| `query_layer3.py` | CLI tool for structured Layer 3 queries with project/scope/privacy filters |
| `search.ps1` | Windows PowerShell wrapper for local search |

**Workspace root resolution:** All scripts use `ANTIGRAVITY_WORKSPACE_ROOT` env var or fall back to two directories above the script file.

---

## 6. Metadata Schema (Layer 3)

Each indexed chunk carries:

```
metadata_version, project, project_slug, scope, privacy,
brain_name, source, source_path, source_file, source_layer,
source_kind, source_heading, source_heading_slug, source_date,
source_timestamp, chunk_index, chunk_count, chunk_chars,
content_hash, indexed_at
```

Privacy defaults by source layer:
- `layer1_stream` → `restricted`
- `layer2_core` → `shareable`
- `layer2_private` → `private`

---

## 7. Cowork Integration (as of 2026-03-10)

Claude Cowork mode is now the active brain sync operator:

- Agent reads public brain layer from this repo
- Synthesizes session update documents (no personal data)
- Commits and pushes via SSH key stored in workspace folder
- Trigger phrase: "push brain update" in Cowork chat

SSH key (ED25519) is persisted in the workspace `.ssh/` folder and registered in GitHub. No token needed for future pushes.

---

## 8. What This Repo Contains vs. Excludes

**Included (public-safe):**
- Architecture documentation
- Operations scripts (`brain/ops/`)
- Phase reports and policy docs
- Session update logs (no personal data)

**Excluded (private/local only):**
- Personal memory (`layer2_private/`)
- Live stream logs (`layer1_stream/`)
- SQLite databases (`layer3_index/`)
- Runtime state (`.sync_state.json`, backups)
- Machine-specific paths

---

## 9. Open Questions

- Phase 4 scope — what belongs in the next upgrade cycle?
- Can Cowork write to `layer2_core` before push (not just reports)?
- Should session update docs move to a `sessions/` folder?
- Evaluate graph overlay (networkx) on top of SQLite for Phase 4
