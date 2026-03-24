# kit/core/kit_invariants.py
# Production-Grade Invariant Enforcement

from typing import Any


class InvariantViolationError(Exception):
    """Lỗi sinh tử: Vi phạm bất biến cấp hệ thống. Yêu cầu dừng ngay lập tức."""

    pass


def enforce(condition: bool, msg: str) -> None:
    """Thay thế hoàn toàn cho assert. Không thể bị bypass bởi cờ -O."""
    if not condition:
        raise InvariantViolationError(f"[FATAL INVARIANT VIOLATION] {msg}")


# --- GLOBAL MEMORY FIREWALL ---

# Only these fields are allowed at the top-level of a GLOBAL entry
ALLOWED_GLOBAL_FIELDS = {
    "id",
    "node_id",
    "content",
    "tag",
    "layer",
    "importance",
    "namespace",
    "scope",
    "structural_hash",
    "is_active",
    "created_at",
    "last_accessed_at",
    "superseded_at",
    "agent_id",
    "commit_id",
    "branch",
    "symbol",
    "materialized_score",
    "supersedes_id",
}

# Only these fields are allowed inside metadata of a GLOBAL entry
# Note: Usually Global entries should have EMPTY metadata, but we allow small provenance.
ALLOWED_GLOBAL_METADATA = {"source", "confidence", "version"}


def sanitize_global_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Tẩy rửa Metadata: Loại bỏ mọi context rác của Local trước khi lên Global."""
    if not metadata:
        return {}
    return {k: v for k, v in metadata.items() if k in ALLOWED_GLOBAL_METADATA}


def enforce_no_global_contamination(entry: dict[str, Any]) -> None:
    """Kiểm tra nhiễm độc: Bắn hạ nếu có bất kỳ trường nào ngoài Whitelist.

    Checks both entry-level fields and metadata-level keys.
    """
    # 1. Check entry level
    illegal_entry_keys: list[str] = [k for k in entry.keys() if k not in ALLOWED_GLOBAL_FIELDS and k != "metadata"]
    enforce(len(illegal_entry_keys) == 0, f"Illegal fields in GLOBAL entry: {illegal_entry_keys}")

    # 2. Check metadata separately
    metadata: dict[str, Any] = entry.get("metadata", {})
    if metadata:
        illegal_meta_keys: list[str] = [k for k in metadata.keys() if k not in ALLOWED_GLOBAL_METADATA]
        enforce(len(illegal_meta_keys) == 0, f"Global Contamination! Metadata chứa trường cấm: {illegal_meta_keys}")

    # 3. Scope check
    enforce(entry.get("scope") in ["GLOBAL", "shared", ""], f"Scope sai lệch cho Global DB: {entry.get('scope')}")


# --- PATH & SPLIT-BRAIN FIREWALL ---


def enforce_path_isolation(proj_a_db: str, proj_b_db: str) -> None:
    enforce(
        proj_a_db != proj_b_db, f"Split Brain / Path Collision phát hiện: {proj_a_db} đang dùng chung với {proj_b_db}"
    )
