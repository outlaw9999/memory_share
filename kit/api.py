import os
from pathlib import Path
from typing import Any

from kit.core.kit_cognitive_core import SAMBrain, SAMBrainError

# --- Stable API Boundary Definitions ---
# This file is the primary entry point for community forks and IDE integrations.

_brain_instance: SAMBrain | None = None


def resolve_paths() -> tuple[Path, Path, Path]:
    """
    Standard Path Resolver for .kit Kernel.
    """
    kit_home = os.getenv("KIT_HOME")
    global_path = Path(kit_home).expanduser() if kit_home else Path.home() / ".kit"
    global_db = global_path / "global.db"
    global_path.mkdir(parents=True, exist_ok=True)

    cwd = Path.cwd().resolve()
    root_path = cwd
    project_db = cwd / ".kit" / "brain.db"

    for parent in [cwd] + list(cwd.parents):
        if (parent / ".kit" / "brain.db").exists():
            root_path = parent
            project_db = parent / ".kit" / "brain.db"
            break
        if (parent / ".git").exists():
            root_path = parent
            project_db = parent / ".kit" / "brain.db"
            break
    
    if not project_db.exists():
        if (root_path / ".git").exists():
            (root_path / ".kit").mkdir(parents=True, exist_ok=True)
            project_db = root_path / ".kit" / "brain.db"
        else:
            (cwd / ".kit").mkdir(parents=True, exist_ok=True)
            project_db = cwd / ".kit" / "brain.db"
            root_path = cwd

    return global_db, project_db, root_path


def init_kernel(db_path: Path | None = None) -> None:
    """Initialize the global SAMBrain instance."""
    global _brain_instance
    global_db, project_db, root_path = resolve_paths()
    target_project_db = db_path if db_path else project_db
    _brain_instance = SAMBrain(target_project_db, root_path=root_path)
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
    supersede_id: int | None = None,
    scope: str | None = None,
    to_global: bool = False,
    symbol: str | None = None,
    structural_hash: str | None = None,
) -> int:
    """Learn a fact with optional symbol anchoring."""
    meta = {"source": "cli", "actor": "human", "agent": "antigravity"}
    if metadata:
        meta.update(metadata)

    return get_brain().learn(
        uid=uid, 
        content=content, 
        kind=kind, 
        importance=importance, 
        layer=layer,
        to_global=to_global,
        supersede_id=supersede_id,
        namespace=namespace,
        scope=scope,
        agent_id=agent_id or meta.get("agent"),
        symbol=symbol,
        structural_hash=structural_hash,
        metadata=meta,
    )


def search(query: str, limit: int = 15, at: str | None = None, agent_id: str | None = None, fast: bool = False) -> list[Any]:
    """Hybrid FTS Search."""
    return get_brain().search(query, limit, at_timestamp=at, agent_id=agent_id, fast=fast)


def recall(entities: list[str], limit: int = 15, at: str | None = None, 
           agent_id: str | None = None, here: bool = False, symbol: str | None = None, fast: bool = False) -> list[Any]:
    """Ranked recall context awareness."""
    return get_brain().recall(entities, limit, at=at, agent_id=agent_id, here=here, symbol=symbol, fast=fast)


def export_prompt(entities: list[str], limit: int = 10, budget: int = 1000) -> str:
    """Renders memory for LLM."""
    return get_brain().export_for_prompt(entities, limit, budget)


def link(src: str, dst: str, rel: str, weight: float = 1.0, metadata: dict[str, Any] | None = None) -> None:
    """Create a semantic link."""
    get_brain().link(src, dst, rel, weight, metadata)


def touch(fact_id: int) -> bool:
    """Reinforce a memory."""
    try:
        get_brain().touch_fact(fact_id)
        return True
    except SAMBrainError:
        return False


def get_blame(symbol: str) -> list[dict]:
    """Retrieve causality chain."""
    return get_brain().get_blame(symbol)


def promote(threshold: int = 5) -> int:
    """Promote memories."""
    return get_brain().promote_memories(threshold)


def stream_events(poll_interval: float = 0.2):
    """Wait and yield semantic memory events."""
    return get_brain().stream_events(poll_interval)


def preflight_check(commit_msg: str, strict: bool = False) -> dict:
    """Run cognitive governance preflight checks."""
    from kit.core.kit_governance import run_preflight
    result = run_preflight(commit_msg=commit_msg, brain=get_brain(), strict_mode=strict)
    import dataclasses
    return dataclasses.asdict(result)


if __name__ == "__main__":
    from kit.cli.main import main
    main()
