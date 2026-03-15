import os
from pathlib import Path
from typing import Any

from kit.core.kit_cognitive_core import SAMBrain, SAMBrainError

# --- Stable API Boundary Definitions ---
# This file is the primary entry point for community forks and IDE integrations.
# Breaking changes here require a major version bump.

_brain_instance: SAMBrain | None = None


def resolve_paths() -> tuple[Path, Path]:
    """
    Standard Path Resolver for .kit Kernel.
    Priority:
    1. ENV KIT_HOME
    2. ~/.kit
    Local project brain is always at ./.kit/brain.db
    """
    kit_home = os.getenv("KIT_HOME")

    if kit_home:
        global_path = Path(kit_home).expanduser()
    else:
        global_path = Path.home() / ".kit"

    project_path = Path.cwd() / ".kit"

    global_db = global_path / "global.db"
    project_db = project_path / "brain.db"

    # Ensure directories exist
    global_path.mkdir(parents=True, exist_ok=True)
    if not project_path.exists():
        # Only create if we are in a project or being proactive
        project_path.mkdir(parents=True, exist_ok=True)

    return global_db, project_db


def init_kernel(db_path: Path | None = None) -> None:
    """
    Initialize the global SAMBrain instance with Hybrid Brain support.
    """
    global _brain_instance

    global_db, project_db = resolve_paths()

    # If explicit db_path is provided, it overrides the project_db
    target_project_db = db_path if db_path else project_db

    _brain_instance = SAMBrain(target_project_db)
    _brain_instance.attach_global(global_db)


def get_brain() -> SAMBrain:
    """Get the initialized SAMBrain instance."""
    if _brain_instance is None:
        init_kernel()
    assert _brain_instance is not None
    return _brain_instance


def learn(
    uid: str,
    content: str,
    kind: str = "observation",
    importance: float = 0.5,
    metadata: dict[str, Any] | None = None,
    layer: str = "episodic",
    namespace: str = "shared",
    agent_id: str | None = None,
) -> int:
    """
    Primary API for an Agent to 'learn' a new observation.
    Automatically injects standard metadata.
    """
    # Standard Metadata Injection
    meta = {
        "source": "cli",
        "actor": "human",
        "agent": "antigravity",
        "origin": "manual",
    }
    if metadata:
        meta.update(metadata)

    return get_brain().learn(
        uid=uid,
        kind=kind,
        content=content,
        importance=importance,
        layer=layer,
        metadata=meta,
        namespace=namespace,
        agent_id=agent_id or meta.get("agent"),
    )


def search(query: str, limit: int = 15, at: str | None = None, agent_id: str | None = None) -> list[Any]:
    """
    Hybrid FTS Search across Project and Global brains.
    """
    return get_brain().search(query, limit, at_timestamp=at, agent_id=agent_id)


def recall(entities: list[str], limit: int = 15, at: str | None = None, agent_id: str | None = None) -> list[Any]:
    """
    Recall ranked context including structural graph expansion.
    """
    return get_brain().recall(entities, limit, at_timestamp=at, agent_id=agent_id)


def export_prompt(
    entities: list[str],
    limit: int = 10,
    budget: int = 1000,
    at: str | None = None,
) -> str:
    """
    Renders memory into compressed XML for LLM injection.
    """
    return get_brain().export_for_prompt(entities, limit, budget)


def link(src: str, dst: str, rel: str, weight: float = 1.0, metadata: dict[str, Any] | None = None) -> None:
    """
    Create a semantic link (edge) between two nodes.
    """
    get_brain().link(src, dst, rel, weight, metadata)


def decay() -> None:
    """Maintenance API for memory decay."""
    get_brain().process_decay()


def touch(fact_id: int) -> bool:
    """Refresh a fact's timestamp (v3.14 compliant)."""
    try:
        get_brain().touch_fact(fact_id)
        return True
    except SAMBrainError:
        return False


if __name__ == "__main__":
    from kit.cli.main import main

    main()
