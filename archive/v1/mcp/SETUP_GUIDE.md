# Antigravity Brain v2 — Setup & Installation Guide

> **GitHub**: https://github.com/outlaw9999/memory_share
> **Purpose**: Long-term shared memory for AI agents (Claude Desktop, Cursor, Cowork)
> **Transport**: Local MCP via stdio — no cloud, no API key

---

## What This Is

`antigravity_mcp` is a local MCP server that exposes the Antigravity brain v2
memory system as 5 tools usable by any MCP-compatible agent.

| Tool | What it does |
|------|-------------|
| `brain_query` | Semantic search Layer 3 memory index (SQLite FTS + re-ranking) |
| `brain_remember` | Write a new memory to layer1_stream for indexing |
| `brain_search_text` | Fast grep across layer2_core Markdown files |
| `brain_status` | Workspace health check + DB record counts |
| `brain_maintain` | Run background consolidation (dry-run safe by default) |

---

## Requirements

- Python **3.10+** — for MCP server, query, write, status, maintain tools
- Python **3.11+** — only for `brain_sync_watcher.py` (live indexing via `neural-memory`)
- `pip install "mcp[cli]>=1.0.0"`

---

## Step 1 — Clone & Initialize (one-time)

```bash
git clone https://github.com/outlaw9999/memory_share.git
cd memory_share

# Install MCP server dependency
pip install "mcp[cli]>=1.0.0"

# Create workspace directories + SQLite schema
python setup_workspace.py

# Verify it works
export ANTIGRAVITY_WORKSPACE_ROOT=/absolute/path/to/memory_share
python brain/mcp/antigravity_mcp.py &   # should start without errors
```

---

## Step 2 — Configure Your Agent

### Claude Desktop

Edit `claude_desktop_config.json`
*(Claude Desktop → Settings → Developer → Edit Config)*

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

Restart Claude Desktop → check that `antigravity` appears in the MCP servers list.

---

### Cursor

In `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

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

---

### Claude Cowork (desktop app)

Cowork cần **hai thứ**: MCP server config + companion skill.

#### 2a. Add MCP server to Cowork

Vào Cowork Settings → MCP Servers → Add:

```json
{
  "antigravity": {
    "command": "python3",
    "args": ["/absolute/path/to/memory_share/brain/mcp/antigravity_mcp.py"],
    "env": {
      "ANTIGRAVITY_WORKSPACE_ROOT": "/absolute/path/to/memory_share"
    }
  }
}
```

#### 2b. Install the companion skill

Skill dạy Claude *khi nào và cách nào* dùng brain tools tự động.

**Cách 1 — Tải file .skill từ GitHub:**
1. Tải [`brain/mcp/antigravity-brain.skill`](https://github.com/outlaw9999/memory_share/raw/main/brain/mcp/antigravity-brain.skill)
2. Mở Cowork → Skills → Install from file → chọn `antigravity-brain.skill`

**Cách 2 — Copy thủ công:**
```bash
cp -r /path/to/memory_share/brain/mcp/antigravity-brain \
      ~/Documents/Claude/skills/antigravity-brain
```

Sau khi install, skill xuất hiện trong danh sách available skills của Cowork.
Claude sẽ **tự động** dùng `brain_query`, `brain_remember`, v.v. khi bạn nói:
- *"nhớ cái này"* / *"lưu lại"* / *"ghi nhớ"*
- *"tìm trong brain"* / *"nhớ lại"* / *"check brain"*
- *"brain_query"* / *"brain_status"* / *"antigravity"*

---

## Step 3 — Verify

Trong bất kỳ agent nào đã cấu hình, gõ:

```
brain status check
```

Output mong đợi:
```
✓ Workspace found at: /your/path/memory_share
✓ Layer 3 database: connected (N neurons, N fibers)
✓ Layer 2 core: N markdown files
✓ Layer 1 stream: N pending files
```

---

## Step 4 (Optional) — Enable Live Indexing

Memories ghi bằng `brain_remember` nằm trong `layer1_stream/` và **chưa searchable**
cho đến khi được index vào Layer 3. Chạy watcher để index real-time (cần Python 3.11+):

```bash
pip install "neural-memory>=2.28.0" "watchdog>=4.0.0"
python brain/ops/brain_sync_watcher.py
```

Hoặc trigger consolidation thủ công bất kỳ lúc nào:
```
brain_maintain(dry_run=False)
```

---

## Usage Examples

### Lưu memory
```
Nhớ lại: hàm login() bị timeout do session expiry sau 15 phút idle.
Fix: tăng SESSION_TIMEOUT lên 30 phút trong config.py
```
→ Claude gọi `brain_remember(heading="Login Timeout Fix", content="...", project="backend")`

### Query trước khi refactor
```
Trước khi refactor auth module, check brain xem có notes gì không
```
→ Claude gọi `brain_status()` rồi `brain_query(query="auth module", project="backend")`

### Kiểm tra health
```
Brain đang chạy không? Có bao nhiêu memory đang index?
```
→ Claude gọi `brain_status()` và báo số lượng neurons/fibers

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTIGRAVITY_WORKSPACE_ROOT` | **Yes** | Absolute path to `memory_share/` repo root |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `"Layer 3 database not found"` | Run `python setup_workspace.py` |
| `"No memories found"` sau khi ghi | `brain_sync_watcher.py` chưa index — chạy một lần |
| `"Maintenance script not found"` | `ANTIGRAVITY_WORKSPACE_ROOT` sai path |
| MCP server không hiện trong Claude Desktop | Check path tuyệt đối; test với `python3 /path/to/antigravity_mcp.py` |
| Skill không trigger trong Cowork | Cần cấu hình MCP server cùng lúc (skill alone không đủ) |

---

## Architecture Quick Reference

```
memory_share/
├── brain/
│   ├── ops/                        # maintenance & indexing scripts
│   │   ├── brain_maintenance.py
│   │   ├── brain_sync_watcher.py   (needs Python 3.11+)
│   │   ├── layer3_backfill.py
│   │   └── layer3_metadata.py
│   └── mcp/
│       ├── antigravity_mcp.py      ← MCP server (agents connect here)
│       ├── antigravity-brain/
│       │   └── SKILL.md            ← Cowork skill (install this)
│       ├── antigravity-brain.skill ← packaged skill file (download & install)
│       └── SETUP_GUIDE.md          ← this file
├── setup_workspace.py              # one-time init
├── requirements.txt
├── .env.example
└── README.md
```

**Memory layers:**
- `layer1_stream/` — raw incoming memories (Markdown files)
- `layer2_core/` — consolidated long-term notes
- `layer3_index/` — SQLite FTS index (`brain.db`) — what `brain_query` searches
