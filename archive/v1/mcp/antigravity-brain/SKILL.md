---
name: antigravity-brain
description: "Long-term memory skill for AI agents using the Antigravity brain v2 MCP system. Use this skill whenever the user wants to: remember or store information for future sessions ('ghi nhớ', 'lưu lại', 'nhớ cái này'), recall past decisions or context ('nhớ lại', 'tìm trong brain', 'check brain'), query what the agent knows about a topic, persist notes/decisions/bug fixes across sessions, or run brain maintenance. Also triggers when the user references the brain system directly ('brain_query', 'brain_remember', 'antigravity', 'layer2', 'layer3'). If the user asks Claude to recall something from a previous session or store something for later, always use this skill first."
requires_mcp: antigravity
---

# Antigravity Brain v2 — Memory Skill

The Antigravity brain is a tiered long-term memory system. Memories live in Markdown files, indexed into a local SQLite graph. Each query injects only the most relevant ~500-token snippet — not full history.

## Quick Reference

| Tool | Khi nào dùng |
|------|-------------|
| `brain_status` | Đầu session mới, kiểm tra brain sẵn sàng chưa |
| `brain_query` | Tìm context liên quan trước khi bắt đầu task |
| `brain_remember` | Lưu quyết định, fix, note quan trọng |
| `brain_search_text` | Tìm nhanh keyword khi chưa index vào Layer 3 |
| `brain_maintain` | Dọn dẹp memory định kỳ |

---

## Standard Workflow

Mỗi khi bắt đầu một task có domain quen thuộc:

```
1. brain_status()            → xác nhận brain ready
2. brain_query(query=topic)  → recall context liên quan
3. [làm việc dựa trên context đã recall]
4. brain_remember(...)       → lưu kết quả/quyết định quan trọng
```

Đừng bỏ qua bước 2 — ngay cả khi user không yêu cầu, context từ brain thường giúp tránh lặp lại công việc đã làm trước đó.

---

## brain_query — Recall memory

Dùng trước khi bắt đầu bất kỳ task nào có thể có lịch sử liên quan.

```python
brain_query(
    query="<chủ đề cần tìm>",
    project="<tên project>",   # optional, lọc theo project
    limit=5,                   # mặc định 5, tối đa 20
    response_format="markdown" # hoặc "json"
)
```

**Khi nào query trả về ít kết quả**: Layer 3 có thể chưa index file mới. Thử `brain_search_text` để tìm trong raw files.

---

## brain_remember — Store memory

Dùng sau khi hoàn thành công việc quan trọng: quyết định thiết kế, bug fix, cấu hình, bài học rút ra.

```python
brain_remember(
    heading="<tiêu đề ngắn gọn>",          # bắt buộc
    content="<nội dung Markdown>",           # bắt buộc, min 10 chars
    project="<project>",                     # mặc định "Root"
    privacy="restricted"                     # shareable | restricted | private
)
```

**Privacy guide**:
- `shareable` — an toàn đẩy lên public repo
- `restricted` (mặc định) — chỉ local
- `private` — không bao giờ rời khỏi layer2_private

Sau khi ghi, file nằm trong `layer1_stream/`. Cần chạy `brain_sync_watcher.py` để index vào Layer 3 để `brain_query` tìm thấy.

---

## brain_search_text — Quick keyword search

Tìm nhanh trong `layer2_core/` không cần DB. Dùng khi:
- Layer 3 chưa index
- Cần kiểm tra keyword tồn tại không trước khi query

```python
brain_search_text(
    query="<từ khóa>",
    include_stream=True,  # cũng tìm trong layer1_stream
    limit=10
)
```

---

## brain_status — Health check

Gọi lần đầu mỗi session hoặc khi gặp lỗi "database not found".

```python
brain_status()
# Returns: workspace path, DB size, record counts, readiness flag
```

Nếu status báo ❌: chạy `python setup_workspace.py` trong thư mục repo.

---

## brain_maintain — Consolidation

Chạy định kỳ (weekly) để dọn duplicate, stale, surface promotion candidates.

```python
brain_maintain(dry_run=True)   # xem trước, không ghi
brain_maintain(dry_run=False)  # áp dụng thay đổi
```

Luôn chạy `dry_run=True` trước. Phase 3 không xóa dữ liệu — chỉ gán tag.

---

## Setup (nếu MCP chưa cấu hình)

MCP server cần được khai báo trong config của agent:

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "python3",
      "args": ["/path/to/memory_share/brain/mcp/antigravity_mcp.py"],
      "env": {
        "ANTIGRAVITY_WORKSPACE_ROOT": "/path/to/memory_share"
      }
    }
  }
}
```

Nếu gặp "MCP tool not found": kiểm tra `ANTIGRAVITY_WORKSPACE_ROOT` đúng chưa, và chạy `python setup_workspace.py` một lần.

---

## Layer model (tham khảo nhanh)

| Layer | Folder | Privacy mặc định |
|-------|--------|-----------------|
| 1 | `layer1_stream/` | restricted |
| 2a | `layer2_core/` | shareable |
| 2b | `layer2_private/` | private |
| 3 | `layer3_index/` (SQLite) | local only |
