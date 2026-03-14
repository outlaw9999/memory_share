# 🏛️ .kit Architecture (v2.0 SAM Epoch)

## 1. Philosophy (Triết lý)
`.kit` là một **Agent Memory Engine**, không phải một framework. Thiết kế dựa trên 3 nguyên tắc bất di bất dịch:
- **Engine-first**: Nhỏ gọn, Zero-Dependency.
- **Immutable memory ledger**: Sự thật là bất biến và có thể truy vết.
- **LLM-agnostic storage**: Không phụ thuộc vào mô hình AI hay Vector Embeddings.

Mục tiêu của `.kit` là trở thành **SQLite cho Agent Memory** — một hạ tầng lưu trữ trí nhớ tất định cho AI Agents.

## 2. Core Architecture (Kiến trúc lõi)
```text
memory_share/
├── runtime/        # Transactional Kernel (ACID cho trí nhớ)
├── kit/
│   ├── api.py      # Public API Boundary (Bản giao kèo ổn định)
│   └── core/       # SAMBrain Cognitive Engine (Ranking & Reasoning)
├── brain/ops/      # Ingestion & Maintenance (Lớp xử lý Layer 1-3)
└── reports/        # Design Documents & Specifications
```

**Workflow:**
`Agent/IDE` ➔ `kit/api.py` ➔ `SAMBrain (Ranking + Reasoning)` ➔ `SQLite Kernel`

---

## 3. Immutable Fact Ledger
`.kit` sử dụng cơ chế **Append-only**. Facts không bao giờ bị xoá hay sửa đổi trực tiếp.
```sql
facts (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER,
    content TEXT,
    importance REAL,
    access_count INTEGER,
    created_at TEXT,
    is_active BOOLEAN DEFAULT 1
)
```
Khi kiến thức thay đổi:
1. **INSERT** fact mới.
2. **SET** `old_fact.is_active = 0`.
Điều này hỗ trợ: **Audit trail**, **Rollback**, và **Time-travel debugging**.

---

## 4. Cognitive Ranking Algorithm
Chúng tôi không sử dụng Vector Search. Ranking dựa trên thuật toán Heuristic tất định:

$$Score = Importance \times \log_{10}(AccessCount + 2) \times \frac{1}{\sqrt{DaysSinceCreated + 1}}$$

| Yếu tố | Vai trò | Chức năng |
| --- | --- | --- |
| **Importance** | Semantic Weight | Trọng số bản thể do Agent/Người dùng gán. |
| **Frequency** | Reinforcement | Càng dùng nhiều điểm càng cao (Log-scale). |
| **Recency** | Forgetting Curve | Phân rã dựa trên thời gian tạo (Square-root). |

---

## 5. Graph Expansion
Recall không chỉ truy vấn Entity chính mà tự động mở rộng sang **1-hop neighbors**.
- *Ví dụ*: Truy vấn `AuthService` sẽ tự động kéo theo các Fact từ `Redis` hoặc `JWT` nếu chúng có liên kết `USES` hoặc `REQUIRES`.

---

## 6. Public API (`kit/api.py`)
Tất cả các tích hợp bắt buộc phải thông qua lớp API này:
- `init_kernel(db_path)`: Khởi tạo engine.
- `learn(uid, kind, content, replaces_id=None)`: Nạp trí nhớ.
- `recall(entities, limit)`: Truy xuất ngữ cảnh đã ranked.
- `export_prompt(entities, limit, budget)`: Kết xuất prompt (XML/Markdown).

---

## 7. Minimal Example
```python
from pathlib import Path
from kit.api import init_kernel, learn, recall

# 1. Khởi tạo Engine (Zero-dependency SQLite)
init_kernel(Path("memory.db"))

# 2. Ghi nhớ (Immutable Fact Ledger)
learn("auth_system", "component", "JWT uses HS256 algorithm")

# 3. Truy xuất (Ranked & 1-Hop Expanded)
memories = recall(["auth_system"], limit=5)

for m in memories:
    print(f"[{m.entity_uid}] -> {m.content}")
```

---

## 8. CLI Interface
CLI của `.kit` chỉ là một lớp vỏ (thin wrapper) gọi trực tiếp vào API:
- `kit learn`
- `kit recall`
- `kit export`

## 9. Design Guarantees
- **Deterministic Ranking**: Cùng dữ liệu, cùng kết quả.
- **Append-only Memory**: Không bao giờ mất lịch sử.
- **LLM-Agnostic**: Trí nhớ thuần túy, không phụ thuộc Model.
- **Zero-Infrastructure**: Chỉ cần SQLite và Python 3.14+.

---

## 11. Long-Term Stability
Sau v2.0 (SAM Epoch), dự án cam kết:
- **Facts Schema**: Đóng băng (Frozen).
- **API Signatures**: Ổn định (Stable).
- **Engine**: Chỉ thêm tính năng, không phá vỡ cấu trúc cũ.
