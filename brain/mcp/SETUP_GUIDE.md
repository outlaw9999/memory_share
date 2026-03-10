# Antigravity MCP — Setup & Usage Guide

## What This Is

`antigravity_mcp` is a local MCP server that exposes the Antigravity brain v2
memory system as 5 tools usable by any MCP-compatible agent (Claude Desktop,
Cursor, Claude Cowork, etc.).

### Tools

| Tool | What it does |
|------|-------------|
| `brain_query` | Semantic search Layer 3 memory index (SQLite FTS + re-ranking) |
| `brain_remember` | Write a new memory to layer1_stream for indexing |
| `brain_search_text` | Fast grep across layer2_core Markdown files |
| `brain_status` | Workspace health check + DB record counts |
| `brain_maintain` | Run background consolidation (dry-run safe by default) |

---

## Requirements

- Python 3.10+ (for MCP server + query/maintenance tools)
- Python 3.11+ (only for `brain_sync_watcher.py` live indexing)
- `pip install mcp[cli]` (see `requirements.txt`)

---

## Quick Start

### 1. Clone and initialize

```bash
git clone https://github.com/outlaw9999/memory_share.git
cd memory_share

# Install MCP server dependency
pip install "mcp[cli]>=1.0.0"

# Initialize workspace directories + SQLite schema
python setup_workspace.py

# Set your workspace root (absolute path to this repo)
export ANTIGRAVITY_WORKSPACE_ROOT=/absolute/path/to/memory_share
```

### 2. Configure Claude Desktop

Edit `claude_desktop_config.json` (find it via Claude Desktop → Settings → Developer):

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_share/brain/mcp/antigravity_mcp.py"],
      "env": {
        "ANTIGRAVITY_WORKSPACE_ROOT": "/absolute/path/to/memory_share"
      }
    }
  }
}
```

Restart Claude Desktop. You should see `antigravity` in the MCP servers list.

### 3. Configure Cursor

In `.cursor/mcp.json` (or global MCP config):

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_share/brain/mcp/antigravity_mcp.py"],
      "env": {
        "ANTIGRAVITY_WORKSPACE_ROOT": "/absolute/path/to/memory_share"
      }
    }
  }
}
```

### 4. Configure Claude Cowork (this tool)

Point Cowork to the MCP server in your workspace settings, or trigger via
Cowork chat: "push brain update" / "query brain for X".

---

## Using the Tools

### Query memory

```
Use brain_query to find what I know about "API login bug" in project "backend"
```

```
brain_query(query="deployment steps", project="infra", limit=5)
```

### Store a memory

```
Use brain_remember to store: heading="Redis Cache Fix", content="Fixed OOM by setting maxmemory-policy allkeys-lru", project="backend"
```

### Check status

```
brain_status()
```

### Run maintenance

```
brain_maintain(dry_run=True)   # safe preview
brain_maintain(dry_run=False)  # apply changes
```

---

## Enable Live Indexing (Python 3.11+)

Memories written via `brain_remember` land in `layer1_stream/` but are not
queryable via `brain_query` until indexed into Layer 3. To enable live indexing:

```bash
# In a Python 3.11+ venv
pip install "neural-memory>=2.28.0" watchdog
python brain/ops/brain_sync_watcher.py
```

Keep the watcher running as a background process or service.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTIGRAVITY_WORKSPACE_ROOT` | Yes | Absolute path to your workspace root |

---

## Troubleshooting

**"Layer 3 database not found"**
→ Run `python setup_workspace.py`

**"No memories found" even though I wrote some**
→ `brain_sync_watcher.py` hasn't indexed yet. Run it once, then retry.

**"Maintenance script not found"**
→ `ANTIGRAVITY_WORKSPACE_ROOT` is pointing to the wrong directory.

**MCP server not appearing in Claude Desktop**
→ Check the path in `claude_desktop_config.json` is absolute and correct.
→ Try: `python3 /path/to/antigravity_mcp.py` — should run without errors.
