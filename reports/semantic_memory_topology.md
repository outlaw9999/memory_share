# ARCHITECTURE REPORT: SEMANTIC MEMORY PAGING (3-LAYER KNOWLEDGE TOPOLOGY)
**Codename:** Anti-Entropy Knowledge Base

---

## 1. VẤN ĐỀ CỦA BỘ NHỚ TUYẾN TÍNH (LINEAR DUMP)

Sai lầm cốt lõi của 90% các hệ thống Agent/Framework hiện tại (như AutoGPT, LangChain) là biến `MEMORY.md` thành một **"Dump log" tuyến tính**. Mọi thứ được append theo thời gian (Session 1, Session 2...).

### Ba hậu quả nghiêm trọng:
1. **Memory becomes Timeline, not Knowledge:** File lưu trữ lịch sử thay vì trạng thái hiện tại. Tỷ lệ Noise/Signal quá cao khiến khả năng suy luận (Reasoning) của LLM bị suy giảm (Degrade).
2. **Context Entropy Explosion:** Khi file phình to (>20k tokens), Agent phải tiêu tốn lượng token khổng lồ chỉ để đọc rác (noise) và cố gắng tự tổng hợp (distill) lại trạng thái hiện tại từ một mớ bòng bong các quyết định bị lặp lại hoặc đảo ngược trước đó.
3. **No Semantic Topology:** Memory không có cấu trúc đồ thị. Tìm kiếm là `O(N)` scan thay vì `O(log N)` retrieval.

### Triết lý:
> **"Project memory ≠ Chat history."**
> **"Timeline → Distill → Knowledge → Memory."**
> **Quy tắc vàng:** Nếu xóa toàn bộ lịch sử (Journal) nhưng giữ lại các file `*.md`, Agent vẫn phải hiểu được toàn bộ dự án hiện tại.

---

## 2. KIẾN TRÚC BỘ NHỚ 3 TẦNG (3-LAYER KNOWLEDGE TOPOLOGY)

Để giải quyết, Antigravity V3 chuyển đổi hoàn toàn sang kiến trúc Memory có cấu trúc ngữ nghĩa (Semantic Partitioning), phân tách rõ ràng giữa Active State, Knowledge, và History.

### Layer 1: Active State (Tầng Trạng thái Tức thì)
- **Files:** `MEMORY.md` (hoặc `STATE.md`), `TASKS.md`
- **Mục đích:** Chỉ chứa trạng thái hiện tại của hệ thống.
- **Nội dung:** "Vào lúc này, kiến trúc là gì? Đang làm dở việc gì?". Hoàn toàn không chứa lịch sử thảo luận.
- **Đặc tính:** Dung lượng cực nhỏ (Low token cost), tải tức thì (Instant load).

### Layer 2: Knowledge Pages (Tầng Tri thức Miền)
- **Files:** Nằm trong `.antigravity/memory/` (VD: `architecture.md`, `decisions.md`, `modules.md`, `bugs.md`, `experiments.md`).
- **Mục đích:** Phân mảnh ngữ nghĩa (Semantic Partitioning).
- **Đặc tính:** Khi Agent cần thông tin về Auth, nó chỉ đọc `memory/auth_module.md` thay vì quyét toàn bộ `MEMORY.md`. Đây là cách hệ Multi-agent đạt được `O(log N)` retrieval.

### Layer 3: Historical Log (Tầng Lịch sử Bất biến)
- **Files:** `.antigravity/memory/journal.jsonl`
- **Mục đích:** Hệ thống Journaling dạng Write-Ahead Log (WAL) ghi lại toàn bộ tiến trình (timeline).
- **Nội dung:** Đây là nơi lưu "Agent A đã nói gì ở Session 1", "Agent B đổi từ JWT sang OAuth vào lúc nào".
- **Đặc tính:** Máy đọc (Machine-readable), append-only, dùng để Rollback hoặc Debug, nhưng **LLM KHÔNG BAO GIỜ tự đọc file này để lấy context chung**.

---

## 3. CƠ CHẾ VẬN HÀNH (MEMORY DRIVER WORKFLOW)

Khi hệ thống có sự thay đổi (Ví dụ: Quyết định chuyển từ JWT sang OAuth):

1. **Ghi History (Layer 3):** Kernel ghi hành động này vào `journal.jsonl`.
2. **Distill Tri thức (Layer 2):** Kernel/Governor tổng hợp quyết định này và cập nhật (hoặc tạo mới) `memory/decisions.md` (ADR - Architecture Decision Records) và cập nhật `memory/auth_module.md`.
3. **Cập nhật State (Layer 1):** Kernel sửa đổi dòng mô tả ngắn gọn trong `MEMORY.md` từ `Auth: JWT` thành `Auth: OAuth`. Các dòng chat thừa của quá trình ra quyết định sẽ hoàn toàn bị loại bỏ khỏi Layer 1 và 2.

---

## 4. BƯỚC TRIỂN KHAI THỰC TẾ TRONG ANTIGRAVITY IDE

Cấu trúc thư mục mới sẽ như sau:

```
workspace/
├── MEMORY.md          (Current overall state)
├── ARCHITECTURE.md    (High-level system design)
├── TASKS.md           (Active work/Checklist)
└── .antigravity/
    └── memory/
        ├── journal.jsonl     (Timeline/WAL)
        ├── decisions.md      (ADRs)
        ├── bugs.md           (Known issues & resolutions)
        ├── experiments.md    (R&D notes)
        └── locks/            (Mutex files for atomic writes)
```

Kiến trúc này biến LLM từ một "Chatbot có trí nhớ dài" thành một **Bộ xử lý trung tâm (CPU)** hoạt động trên một **Hệ thống tệp nhận thức (Cognitive File System)** được quản lý cấu trúc chặt chẽ.
