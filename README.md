# kit — remember things from your terminal. 🧠

**kit** is a tiny, infrastructure-grade memory engine for humans and AI agents. It's a **Temporal Quad-Store** built for the Unix workflow.

---

### 1️⃣ Instant Identity

**kit — git-like memory for developers.**
A zero-dependency, local-first primitive to store and recall useful facts.

### 2️⃣ 5-Second Demo

```bash
# Learn something with context (Metadata support)
kit learn --content "JWT fails because of clock skew" --uid auth --meta tags=bug,security

# Recall it instantly
kit recall auth
# Output: • [auth] JWT fails because of clock skew

# Time-travel (Snapshot)
kit recall auth --at "2026-03-01"
```

### 3️⃣ Why this exists?

Notes are disconnected from your terminal. Vector DBs are overkill and non-deterministic.

- **kit** is deterministic: Same data, same rank.
- **kit** is fast: ~10ms search on 1M facts.
- **kit** is temporal: It remembers what you knew *last week*.

### 4️⃣ Pain → Solution

| Problem | Solution |
| --- | --- |
| Forget why code exists | `kit learn arch` |
| Lose track of bug fixes | `kit learn bug` |
| Search history for AI | `kit recall` |
| Knowledge evolution | `kit recall --at "7 days ago"` |

### 5️⃣ Composability

Built to be piped. No fancy UI, just raw power.

```bash
# Fuzzy search your memories
kit recall | fzf

# Search historical bugs and pipe to AI agent
kit recall bug --at "2026-03-01" | aider
```

### 6️⃣ Where data lives

All data is stored locally in a single, standard SQLite file:
`~/.kit/brain.db` (WAL mode enabled for concurrency).

### 7️⃣ Philosophy

**Do one thing well.** `.kit` is a memory primitive, not a platform. It's the `sqlite` for your personal and agentic knowledge.

---

### 🏛️ Engineering Specs (Elite Architecture)
- **Engine**: SQLite FTS5 (External Content) + Porter Tokenizer.
- **Model**: Unified 4-Table Truth (Nodes, Observations, Edges, Keyword Index).
- **Temporal logic**: Lineage snapshotting via `created_at` / `superseded_at`.
- **Latency**: 3-20ms @ 1,000,000 facts.
- **License**: MIT
