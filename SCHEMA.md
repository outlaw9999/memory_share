# .kit SAM Schema v1.0 (The Data Contract)

Cơ sở dữ liệu của `.kit` (Structured Agent Memory - SAM) được lưu trữ trong SQLite, tuân thủ mô hình **Graph-Episodic Hybrid**.

## 1. Nguyên lý Bất biến (Immutable Ledger)
Trí nhớ trong `.kit` là **Append-only**. Chúng tôi không bao giờ `DELETE` hay `UPDATE` nội dung của bảng `facts`.
- Khi kiến thức mới thay thế kiến thức cũ, bản ghi cũ được đánh dấu `is_active = 0`.
- Điều này cho phép Audit toàn bộ quá trình tiến hóa nhận thức của Agent.

## 2. Các bảng cốt lõi (Core Tables)

### `entities`
Lưu trữ các "Node" trong Knowledge Graph.
- `uid`: Mã định danh duy nhất (Unique ID).
- `kind`: Loại thực thể (Component, File, Class, Logic, v.v.).

### `facts`
Lưu trữ các "Sự thật" nguyên tử gắn liền với thực thể.
- `content`: Nội dung ngữ nghĩa (văn bản thuần).
- `is_active`: Trạng thái (1: Active, 0: Superseded).
- `importance`: Trọng số độ quan trọng cốt lõi (0.1 - 1.0).
- `access_count`: Tần suất được truy xuất (Frequency).
- `created_at`: Dấu mốc thời gian (Recency).

### `relations`
Lưu trữ các "Edge" (Cạnh) liên kết các Node.
- `source_id`, `target_id`: Các thực thể liên quan.
- `type`: Loại quan hệ (USES, DEPENDS_ON, IMPLEMENTS, v.v.).
- `weight`: Độ mạnh của liên kết.

---

## 3. Thuật toán Xếp hạng (Ranking Equation)

Điểm số của một Fact được tính toán tại tầng SQL Engine:

$$Score = Importance \times \log_{10}(AccessCount + 2) \times \frac{1}{\sqrt{\max(1, DaysOld)}}$$

Hàm này đảm bảo sự cân bằng giữa:
- **Tầm quan trọng** (Importance)
- **Tần suất sử dụng** (Frequency)
- **Độ tươi mới** (Recency)
