---
name: antigravity-brain
version: 1.0.0
description: >
  Long-term memory skill for AI agents using the Antigravity brain v2 system.
  Use this skill to store and retrieve memories across sessions via MCP tools.
requires_mcp: antigravity
python: ">=3.10"
---

# Antigravity Brain — Agent Skill

This skill connects any MCP-compatible agent to the Antigravity brain v2
memory system. It enables persistent long-term memory across sessions.

---

## When to Use

Use this skill when:
- The user asks you to "remember" something for future sessions
- You need context from past sessions ("what did we decide about X?")
- You want to check what's already known before starting a task
- You need to log a decision, fix, or note that should persist

---

## Tool Reference

### `brain_query` — Recall memories

**Use for**: Finding relevant context before starting work.

```
brain_query(
  query="what do I know about <topic>",
  project="<project_name>",   # optional
  limit=5
)
```

**Best practice**: Call this at the start of any task in a domain where
the user may have stored relevant history.

---

### `brain_remember` — Store a memory

**Use for**: Persisting important decisions, fixes, or notes.

```
brain_remember(
  heading="<Short title of the memory>",
  content="<Markdown content — can be multi-paragraph>",
  project="<project_name>",     # default: "Root"
  privacy="restricted"          # shareable | restricted | private
)
```

**Privacy guide**:
- `shareable` — safe to sync to public repo
- `restricted` — local only, not private
- `private` — never leaves layer2_private

---

### `brain_search_text` — Quick keyword search

**Use for**: Fast lookup when you know the exact term.

```
brain_search_text(query="<keyword>", include_stream=True)
```

---

### `brain_status` — Check if brain is ready

**Use for**: Confirming setup before first query.

```
brain_status()
```

---

### `brain_maintain` — Consolidate memory

**Use for**: Periodic cleanup of old/duplicate memories.

```
brain_maintain(dry_run=True)   # preview
brain_maintain(dry_run=False)  # apply
```

---

## Standard Workflow

```
1. brain_status()                          # verify brain is ready
2. brain_query(query="<relevant topic>")   # recall context
3. [do work using recalled context]
4. brain_remember(heading="...", ...)      # persist key outcomes
```

---

## Example Agent Prompt

> Before starting any task, check the brain for relevant context:
> 1. Call `brain_status()` to confirm the brain is initialized.
> 2. Call `brain_query(query="<task topic>")` to retrieve relevant memories.
> 3. Use retrieved context to inform your work.
> 4. After completing important work, call `brain_remember()` to persist key decisions.

---

## Setup Checklist

- [ ] Cloned `memory_share` repo
- [ ] Ran `python setup_workspace.py`
- [ ] Set `ANTIGRAVITY_WORKSPACE_ROOT` env variable
- [ ] Added `antigravity_mcp.py` to MCP server config
- [ ] (Optional) Running `brain_sync_watcher.py` for live indexing (Python 3.11+)
