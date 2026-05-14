from kit.memory.projection import MemoryProjection, ProjectionReceipt, ProjectionRequest

# Legacy CLI-centric API (may fail — kept for backward compat only)
try:
    from kit.api import learn, recall, recall_with_assessment  # type: ignore
    from kit.api import reflect_check as reflect
    from kit.core.deterministic_context import get_deterministic_context as context  # type: ignore
    _legacy_ok = True
except Exception:
    learn = recall = reflect = context = recall_with_assessment = None  # type: ignore
    _legacy_ok = False

__all__ = [
    "MemoryProjection", "ProjectionRequest", "ProjectionReceipt",
]
