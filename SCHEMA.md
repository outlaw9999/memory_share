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
- `metadata`: JSON escape hatch để mở rộng các thuộc tính tùy ý.

### `facts`
Lưu trữ các "Sự thật" nguyên tử gắn liền với thực thể.
- `content`: Nội dung ngữ nghĩa (văn bản thuần).
- `metadata`: JSON escape hatch (Ví dụ: `{"tags": ["ai", "infra"]}`).
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

## 3. Search Indexing (FTS5 & Triggers)

`.kit` sử dụng **FTS5 External Content** để đảm bảo hiệu suất tìm kiếm tối đa mà không làm phình DB.

- **Bảng ảo `facts_fts`**: Ràng buộc trực tiếp với `facts(id, content)` thông qua bộ lọc `porter`.
- **Đồng bộ hóa tức thì**: Sử dụng bộ 3 Triggers (`facts_ai`, `facts_au`, `facts_ad`) để đảm bảo Index luôn khớp với dữ liệu thật tại bảng `facts`.

---

## 4. Thuật toán Xếp hạng (Ranking Equation)

Điểm số của một Fact được tính toán tại tầng SQL Engine sử dụng **Half-life Exponential Decay**:

$$Score = Importance \times \log_{10}(AccessCount + 2) \times \frac{1}{1 + (DaysOld / 30)}$$

Hàm này đảm bảo sự cân bằng giữa:
- **Tầm quan trọng** (Importance)
- **Tần suất sử dụng** (Frequency)
- **Độ bền vững** (Longevity): Một thông tin quan trọng sẽ không bị quên lãng quá nhanh.
