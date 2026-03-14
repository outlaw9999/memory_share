# .kit Engine API v1.0 (Stable Boundary)

Toàn bộ sức mạnh của `.kit` được đóng gói trong tệp `kit/api.py`. Các IDE fork và Agent Framework chỉ nên giao tiếp thông qua các hàm này.

## 1. Khởi tạo (Bootstrap)

```python
from pathlib import Path
from kit import api

api.init_kernel(Path("my_memory.db"))
```

## 2. Giao diện nhận thức (Cognitive API)

### `learn(entity_uid, kind, content, importance=0.5, replaces_id=None)`
Ghi lại một sự thật mới. Nếu `replaces_id` được cung cấp, trí nhớ cũ sẽ được đánh dấu ngừng hoạt động.
- Trả về: `fact_id` (int).

### `recall(query_entities, limit=15)`
Truy xuất danh sách `MemoryNode` đã được xếp hạng và mở rộng theo đồ thị (1-hop expansion).

### `export_prompt(query_entities, limit=10, budget=1000)`
Kết xuất trí nhớ thành chuỗi Markdown/XML tối ưu hóa Token để nhét trực tiếp vào System Prompt của LLM.

### `link_entities(src, dst, rel, weight=1.0)`
Liên kết hai thực thể trong Knowledge Graph để làm giàu context cho bước `recall`.

---

## 3. Tích hợp CLI
Ngài có thể gọi trực tiếp từ Terminal để đảm bảo kiến trúc không trạng thái (Stateless):
```bash
python -m kit.cli.main learn --uid "Auth" --content "Uses HS256"
python -m kit.cli.main recall --entities "Auth"
```
