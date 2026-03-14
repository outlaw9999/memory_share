from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from kit.core.kit_cognitive_core import SAMBrain, Memory, SAMBrainError

# --- Stable API Boundary Definitions ---
# This file is the primary entry point for community forks and IDE integrations.
# Breaking changes here require a major version bump.

_brain_instance: Optional[SAMBrain] = None

def init_kernel(db_path: Path) -> None:
    """Initialize the global SAMBrain instance."""
    global _brain_instance
    _brain_instance = SAMBrain(db_path)

def get_brain() -> SAMBrain:
    """Get the initialized SAMBrain instance."""
    if _brain_instance is None:
        raise SAMBrainError("SAMBrain kernel not initialized. Call init_kernel(db_path) first.")
    return _brain_instance

def learn(
    entity_uid: str, 
    kind: str, 
    content: str, 
    importance: float = 0.5, 
    source: str = "agent_session",
    replaces_id: Optional[int] = None
) -> int:
    """
    Primary API for an Agent to 'learn' a new fact about a system.
    This operation is append-only for auditability.
    """
    return get_brain().learn_fact(
        entity_uid=entity_uid,
        kind=kind,
        content=content,
        importance=importance,
        source=source,
        supersedes_id=replaces_id
    )

def recall(query_entities: List[str], limit: int = 15) -> List[Memory]:
    """
    Primary API to retrieve ranked context, including 1-hop graph expansion.
    """
    return get_brain().recall_context(query_entities, limit)

def export_prompt(query_entities: List[str], limit: int = 10, budget: int = 1000) -> str:
    """
    Renders memory into a compressed XML/Markdown format for LLM injection.
    """
    return get_brain().export_for_prompt(query_entities, limit, budget)

def link_entities(src: str, dst: str, rel: str, weight: float = 1.0) -> None:
    """
    Manually create a directed semantic link between two entities.
    """
    get_brain().link(src, dst, rel, weight)

def decay_memory(factor: float = 0.99) -> None:
    """
    Maintenance API to simulate artificial forgetting (Recency/Importance balance).
    """
    get_brain().process_decay(factor)
