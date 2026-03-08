# 🧠 Antigravity Memory Kernel

## Journaling Logic & Memory Driver Specification (v0.1)

Subsystem này đóng vai trò:
`AI Memory Write Boundary`

Nó bảo vệ hệ file-based memory (`.md`) khỏi:
* Write contention
* Crash corruption
* Context drift
* Cognitive race conditions

Kiến trúc mượn từ:
* **Write-Ahead Logging (WAL)**
* **Shadow Paging**
* **Filesystem Journaling**

---

## 1. Overall Architecture

Pipeline đầy đủ:
```text
Agent
   ↓
Memory Driver
   ↓
Lock Manager
   ↓
Journal (WAL)
   ↓
Atomic Shadow Write
   ↓
Markdown Memory Files

Watcher
   ↓
Layer3 SQLite Index
```

Các module:
```text
runtime/
   memory_driver.py
   lock_manager.py
   journal_engine.py
   paging_engine.py
```

---

## 2. Locking Mechanism

Locking được thiết kế **multi-tier**.
Không dùng graph lock vì gây nghẽn.

### Tier 1 — Domain Lock
Ngăn nhiều agent sửa cùng **semantic domain**.
Ví dụ: `memory/domains/auth.md`, `memory/domains/database.md`
Lock file: `.antigravity/memory/locks/domain_auth.lock`

### Tier 2 — File Lock
Bảo vệ file thực tế.
Ví dụ: `brain/layer2_core/auth.md`
Lock: `.antigravity/memory/locks/auth_md.lock`

### Lock Structure
```json
{
  "lock_id": "uuid",
  "agent": "worker_auth_refactor",
  "resource": "auth.md",
  "created_at": "2026-03-08T10:12:33Z",
  "ttl": 300,
  "pid": 42311
}
```

### Deadlock Handling
Governor chạy job: `lock_gc_worker`
Logic: `if now - created_at > ttl: kill_agent(); release_lock()`
Recovery: `git restore target_file`

---

## 3. Journal (Write-Ahead Log)

File: `.antigravity/memory/journal.jsonl`
Format: JSONL (Mỗi transaction một dòng)

### Journal Record Schema
```json
{
  "txn_id": "uuid",
  "timestamp": "2026-03-08T10:15:44Z",
  "agent": "agent_planner",
  "operation": "update",
  "target_file": "brain/layer2_core/auth.md",
  "lock_id": "uuid",
  "old_hash": "sha256",
  "new_hash": "sha256",
  "shadow_file": ".shadow/auth_md_2342.tmp",
  "status": "pending"
}
```
Status states: `pending, committed, rolled_back`

---

## 4. Atomic Shadow Paging

Cơ chế **safe write**, không ghi trực tiếp `.md`.

Flow:
1. agent request write
2. acquire lock
3. write shadow page
4. journal append
5. atomic rename
6. commit journal
7. release lock

### Shadow Page Location
`.antigravity/memory/shadow/auth_md_txn_483.tmp`

### Atomic Commit
`os.replace(shadow_file, target_file)` (Atomic trên Linux, Mac, Windows NTFS)

### Crash Recovery
Khi system restart: scan `journal.jsonl`.
Nếu `status == pending` thì `rollback` hoặc `commit if shadow exists`.

---

## 5. Mapping JSON Transaction → Markdown

Agent không ghi raw text. Agent gửi patch dạng structured.
Example:
```json
{
  "operation": "append",
  "target": "brain/layer2_core/auth.md",
  "section": "## API Tokens",
  "content": "- token rotation policy updated"
}
```

Memory driver:
1. parse markdown AST (e.g., via `markdown-it` or `mistune`)
2. locate section
3. apply patch
4. generate new file

---

## 6. Knowledge Paging Engine

Markdown memory cần tránh unbounded growth.
Kernel áp dụng **working set model**:
- **Active Page:** `MEMORY.md` (recent high-value knowledge)
- **Archive Memory:** `ARCHIVE.md` hoặc `archives/*.md`

### Paging Trigger
Paging chạy khi: `file_size > 4 KB` or `entries > 50`

---

## 7. Distillation Algorithm

Kernel thực hiện **knowledge compression**.
Flow: `select old entries → cluster by topic → summarize → archive raw`

Example Before `MEMORY.md`:
- 2026-02 auth bug
- 2026-02 auth patch
- 2026-02 auth refactor

After `MEMORY.md`:
"Auth system stabilized Feb 2026. Major fixes applied to token lifecycle"
Archive: `archives/auth_2026_02.md`

---

## 8. Background Maintenance

Worker: `brain_maintenance.py`
Jobs: `dedupe, stale detection, promotion, archive paging`
Schedule: every 30 minutes

---

## 9. Final Architecture (AI Memory OS)

```text
Agents
   ↓
Planner
   ↓
Memory Driver
   ↓
Lock Manager
   ↓
Journal (WAL)
   ↓
Shadow Paging
   ↓
Markdown Memory

Watcher
   ↓
SQLite Metadata Index

Maintenance Worker
   ↓
Knowledge Distillation
```
Đây là kiến trúc của một **AI Cognitive Kernel**.
