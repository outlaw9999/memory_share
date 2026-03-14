# ARCHITECTURE REPORT: AGENT TRANSACTIONS & CONTEXT LOCKS
**Codename:** Cognitive Isolation Protocol

---

## 1. VẤN ĐỀ TRANH CHẤP NHẬN THỨC (COGNITIVE RACE CONDITIONS)

Khi Antigravity thăng cấp từ một công cụ đơn lẻ lên hệ sinh thái Multi-Agent (với Gemini CLI, OpenClaw chạy song song), một tình huống tàn khốc (fatal flaw) xuất hiện:
**"Memory Corruption via Concurrent Edits"** (Hỏng bộ nhớ do chỉnh sửa đồng thời).

### Kịch bản thảm họa:
- **Agent A (Auth Worker)** đọc `auth_service.ts` và bắt đầu tốn 30 giây suy luận (LLM reasoning).
- **Agent B (Billing Worker)** đổi interface truyền vào `auth_service.ts` và ghi đè file trong lúc Agent A đang suy luận.
- **Agent A (Auth Worker)** kết thúc suy luận, ghi đè lại file `auth_service.ts` dựa trên phiên bản cũ.
→ Dữ liệu của Agent B bị xóa sổ. Hệ thống sập (Build Failed).
→ Giống hệt sự cố xóa nhầm ổ D: do Agent mất đồng bộ ngữ cảnh (Context drift).

Để giải quyết, Antigravity V3 yêu cầu cơ chế **Agent Transactions** với chiến lược khóa đa tầng (Multi-tier Locks).

---

## 2. CHIẾN LƯỢC KHÓA ĐA TẦNG (MULTI-TIER LOCKING)

Chúng ta không sử dụng *Graph Lock* (quá nặng, khóa toàn bộ cây phụ thuộc gây tắc nghẽn), cũng không dùng *Transaction Lock* truyền thống (Database-style). 

Antigravity sử dụng **Hybrid Domain & File Locks (Khóa Miền & Khóa Tệp kết hợp)**.

### A. Level 1: Domain Locks (Khóa Mức Ngữ Nghĩa)
- Dùng để chống dẫm chân lên trí nhớ tập thể (Semantic Memory).
- Khi **Agent A** được giao refactor "Auth", Kernel tạo một File Lock bí mật: `.antigravity/memory/locks/domain_auth.lock`.
- Hành vi: **Agent B** vẫn có thể *đọc* `auth.md`, nhưng **tuyệt đối không được ghi** (Read-only) cho đến khi Agent A hoàn tất Transaction và release lock.
- Bảo vệ: `memory/domains/auth.md`

### B. Level 2: File-level Write Locks (Khóa Mức Tệp Tồn tại Thực)
- Dùng để ngăn chặn Race Condition cứng trên mã nguồn.
- Trước khi thực thi lệnh ghi (ví dụ lệnh `sed` hoặc Replace của MCP), Agent phải xin quyền Kernel để tạo `.antigravity/memory/locks/src_auth_service.ts.lock`.
- Nếu file đang bị khóa bởi Worker khác, Kernel sẽ trả về `HTTP 423 Locked` (tín hiệu MCP), bắt buộc Agent phải tạm dừng, cập nhật lại Context, và thử lại.
- Tránh được lỗi ngớ ngẩn: 2 Agent sửa cùng 1 file dẫn đến Conflict Merge.

---

## 3. VÒNG ĐỜI MỘT GIAO DỊCH NHẬN THỨC (COGNITIVE TRANSACTION LIFECYCLE)

Để ngăn chặn lỗi "Tự phá Codebase", mọi hành động chỉnh sửa của Agent trong hệ AI-OS phải tuân thủ chuẩn ACID (Atomicity, Consistency, Isolation, Durability) nhái lại từ Database:

```text
[BẮT ĐẦU MISSION]
   ↓
1. REQUEST LOCKS: Agent yêu cầu Domain Lock (ví dụ: auth) và Target File Locks (những file dự định sửa).
   ↓
2. READ STATE: Chỉ sau khi lấy được Lock, Agent mới đọc `STATE.md`, `memory/domains/auth.md` và mã nguồn (Đảm bảo đọc bản mới nhất).
   ↓
3. REASONING (LLM CPU): Agent tiêu tốn token để suy nghĩ.
   ↓
4. CONSTITUTION GUARD: Đề xuất sửa đổi bị ném qua `coding_invariants.md`. (Nếu vi phạm → Abort, Release Lock).
   ↓
5. ATOMIC WRITE: Kernel thực hiện ghi mã nguồn. (Hoặc thành công 100%, hoặc Git Checkout rollback).
   ↓
6. JOURNAL APPEND: Kernel ghi hành động vào `journal.jsonl`.
   ↓
7. DISTILL KNOWLEDGE: Cập nhật `memory/domains/auth.md`.
   ↓
8. RELEASE LOCKS: Giải phóng toàn bộ `.lock` files.
   ↓
[KẾT THÚC MISSION]
```

---

## 4. BẢO VỆ CHỐNG RỦI RO (DEADLOCK PREVENTION)

Nếu một tác vụ quá khó khiến Agent bị treo (LLM timeout) trong khi nó đang giữ `auth.lock`, toàn bộ dự án sẽ kẹt?

**Giải pháp (TTL - Time to Live):** 
Mọi file lock sinh ra đều có chứa `timestamp` bên trong. 
Ví dụ nội dung file lock: `{"agent_id": "gemini-mcp-1", "expires_at": 1740005000}`.
Nếu Timeout (quá 5 phút), Governor (Tổng quản) có quyền **Kill Agent** đó, tự động `git restore` file đang sửa dở, và giải phóng Lock cho Agent khác.

---

## 5. TỔNG KẾT: KIẾN TRÚC HOÀN HẢO

Với cơ chế Locks này, Antigravity IDE thực sự biến thành một **AI Software Factory** nơi:
1. `gemini` (Worker A) sửa Font-end.
2. `gemini` (Worker B) viết Backend.
3. `openclaw` (Worker C) viết Test.
Tất cả chạy song song, chia sẻ cùng Memory Paging, tuân thủ Constitution Guard, và không bao giờ giẫm chân lên nhau nhờ Domain/File Locks.
