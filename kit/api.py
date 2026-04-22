import os
import uuid
from pathlib import Path
from typing import Any

from kit.core.kit_cognitive_core import RankingAssessment, SAMBrain, SAMBrainError
from kit.core.rmil import warmup_memory # RMIL v1.0
from kit.core.memory_topology import MemoryTopologyFactory

# v1.2.4-LOCK: Vantage is external-binary-only; called from kit_baking, NOT from learn().

# --- Stable API Boundary Definitions ---
# This file is the primary entry point for community forks and IDE integrations.

_brain_instance: SAMBrain | None = None

from kit.core.kit_replay_tracer import traced


def resolve_paths(force_local: bool = False, mode: str = "auto") -> tuple[Path, Path, Path]:
    """
    Standard Path Resolver for .kit Kernel. (v1.2.4-COLLAPSE)
    """
    cwd = Path.cwd().resolve()
    
    if force_local or mode == "isolated":
        root_path = cwd
        # v1.2.4 Debug
        if os.getenv("KIT_LOG_LEVEL") == "DEBUG":
            import logging
            logging.getLogger("kit.api").debug(f"resolve_paths(force_local=True) -> root_path={root_path} (cwd={cwd})")
    else:
        # Determine repo boundary (.git) as the absolute ceiling
        repo_root = None
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                repo_root = parent
                break
        
        # Walk up to find .kit directory
        root_path = cwd
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".kit").exists():
                root_path = parent
                break
            if repo_root and parent == repo_root:
                root_path = parent
                break

    # v1.2.4-COLLAPSE: Authority resolution via MemoryTopology
    topology = MemoryTopologyFactory.for_project(root_path)
    global_db = topology.resolve("global", "global")
    project_db = topology.resolve("local", "local")

    return global_db, project_db, root_path


# @epistemic: init_kernel
def init_kernel(db_path: Path | None = None, mode: str = "auto") -> None:
    """Initialize the global SAMBrain instance."""
    global _brain_instance
    global_db, project_db, root_path = resolve_paths(mode=mode)
    target_project_db = db_path if db_path else project_db
    _brain_instance = SAMBrain(target_project_db, root_path=root_path)
    _brain_instance.attach_global(global_db)
    
    # --- RMIL v1.0: Warmup working memory ---
    from kit import api
    warmup_memory(api)


def get_brain() -> SAMBrain:
    """Get the initialized SAMBrain instance."""
    if _brain_instance is None:
        init_kernel()
    assert _brain_instance is not None
    return _brain_instance


def shutdown_kernel() -> None:
    """Shutdown the cognitive kernel background tasks."""
    global _brain_instance
    if _brain_instance is not None:
        _brain_instance.shutdown()
        _brain_instance = None


# @epistemic: learn
@traced("api.learn")
def learn(
    content: str,
    tag: str = "decision",
    uid: str | None = None,
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
    skip_render: bool = False,
) -> int:
    """
    Learn a fact. v1.2.4-LOCK: Pure O(1) write. No Vantage. No structural analysis.
    Structural graduation happens via `kit bake` (explicit baking pass) or `kit reflect`.
    """
    brain = get_brain()
    meta = {"source": "cli", "actor": "human", "agent": "antigravity"}
    if metadata:
        meta.update(metadata)

    resolved_uid = uid if uid else str(uuid.uuid4())

    return brain.learn(
        uid=resolved_uid,
        content=content,
        tag=tag,
        node_type=kind,
        importance=importance,
        layer=layer,
        namespace=namespace,
        agent_id=agent_id,
        to_global=to_global,
        supersede_id=supersede_id,
        scope=scope,
        metadata=meta,
        symbol=symbol,
    )


import functools

@functools.lru_cache(maxsize=32)
def _cached_search(query: str, limit: int, at: str | None, agent_id: str | None, fast: bool) -> list[Any]:
    return get_brain().search(query, limit, at_timestamp=at, agent_id=agent_id, fast=fast)

# @epistemic: search
@traced("api.search")
def search(
    query: str, limit: int = 15, at: str | None = None, agent_id: str | None = None, fast: bool = False
) -> list[Any]:
    """Hybrid FTS Search with LRU Cache (v1.2.3-STABLE)."""
    return _cached_search(query, limit, at, agent_id, fast)


@functools.lru_cache(maxsize=32)
def _cached_recall(
    entities_t: tuple[str, ...],
    limit: int,
    at: str | None,
    agent_id: str | None,
    here: bool,
    symbol: str | None,
    query: str | None,
    with_global: bool,
    fast: bool,
    include_profile: bool,
    since: str | None = None,
    until: str | None = None,
) -> tuple[list[Any], dict[str, float] | None]:
    return get_brain().recall(
        list(entities_t),
        limit,
        at=at,
        agent_id=agent_id,
        here=here,
        symbol=symbol,
        query=query,
        with_global=with_global,
        fast=fast,
        include_profile=include_profile,
        since=since,
        until=until
    )

# @epistemic: recall
@traced("api.recall")
def recall(
    entities: list[str],
    limit: int = 15,
    at: str | None = None,
    agent_id: str | None = None,
    here: bool = False,
    symbol: str | None = None,
    query: str | None = None,
    with_global: bool = False,
    fast: bool = False,
    include_profile: bool = False,
    since: str | None = None,
    until: str | None = None,
) -> list[Any] | tuple[list[Any], dict[str, float] | None]:
    """Ranked recall context awareness with LRU Cache (v1.2.3-STABLE)."""
    result = _cached_recall(
        tuple(entities) if entities is not None else (),
        limit,
        at,
        agent_id,
        here,
        symbol,
        query,
        with_global,
        fast,
        include_profile,
        since,
        until
    )
    if include_profile:
        return result  # Already a tuple (memories, profile)
    return result  # Just the memories list


def recall_with_assessment(
    entities: list[str],
    limit: int = 15,
    at: str | None = None,
    agent_id: str | None = None,
    here: bool = False,
    symbol: str | None = None,
    with_global: bool = False,
    fast: bool = False,
) -> RankingAssessment:
    """Ranked recall plus confidence / ambiguity metadata."""
    return get_brain().recall_with_assessment(
        entities,
        limit=limit,
        at=at,
        agent_id=agent_id,
        here=here,
        symbol=symbol,
        with_global=with_global,
        fast=fast,
    )


# @epistemic: link
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


def get_blame(symbol: str) -> list[dict[str, Any]]:
    """Retrieve causality chain."""
    return get_brain().get_blame(symbol)


def promote(threshold: int = 5) -> int:
    """Promote memories."""
    return get_brain().promote_memories(threshold)


def stream_events(poll_interval: float = 0.2):
    """Wait and yield semantic memory events."""
    return get_brain().stream_events(poll_interval)


def snapshot() -> Path:
    """Manual trigger for database snapshot (v1.2.4)."""
    return get_brain().snapshot()


def restore(snapshot_path: Path | None = None) -> bool:
    """Restore kernel from a physical snapshot."""
    return get_brain().restore(snapshot_path)


# @epistemic: preflight_check
def preflight_check(commit_msg: str, strict: bool = False, diff_text: str | None = None) -> dict[str, Any]:
    """Run cognitive governance preflight checks."""
    import dataclasses

    from kit.core.kit_governance import run_preflight

    result = run_preflight(commit_msg=commit_msg, brain=get_brain(), strict_mode=strict, diff_text=diff_text)
    return dataclasses.asdict(result)


# @epistemic: reflect_check
@traced("api.reflect_check")
def reflect_check(
    diff_text: str | None = None,
    scope: str | None = None,
    external_signals: list[Any] | None = None,
    file_path: Path | None = None,
    deep: bool = False
) -> dict[str, Any]:
    """Run cognitive reflection check (v1.2.4 TITANIUM)."""
    from kit.core.kit_platform import GIT_TIMEOUT, run_safe
    from kit.core.kit_reflect import run_reflect

    if diff_text is None:
        try:
            # Check for staged changes first
            res = run_safe(["git", "diff", "--cached"], timeout=GIT_TIMEOUT)
            diff_text = res.stdout
            if not diff_text:
                # Fallback to current changes
                res = run_safe(["git", "diff", "HEAD"], timeout=GIT_TIMEOUT)
                diff_text = res.stdout
        except Exception:
            # FALLBACK: Return empty diff to prevent IDE freeze if git hangs or fails
            diff_text = ""

    report = run_reflect(
        get_brain(),
        diff_text,
        scope=scope,
        external_signals=external_signals,
        file_path=file_path,
        deep=deep
    )

    # MEC v1: Map unified signals to legacy issue format for backward compatibility
    issues: list[dict[str, str]] = []
    for sig in report.signals:
        issues.append(
            {
                "type": "signal",
                "uid": sig.uid,
                "message": sig.evidence or f"Signal detected: {sig.uid}",
                "confidence": sig.confidence,
                "source": sig.source
            }
        )

    return {
        "score": report.score,
        "status": report.status,
        "signals": [s.model_dump() if hasattr(s, "model_dump") else s for s in report.signals],
        "issues": issues,
        "suggestions": report.suggestions,
        "confirmations": report.confirmations
    }


# --- Procedural Skill Layer (L3) ---

def list_procedural_skills() -> list[dict[str, Any]]:
    """List all compiled YAML-based skills in the brain."""
    from kit.skills.matcher import list_procedural_skills
    return list_procedural_skills()


def trigger_skill(message: str, dry_run: bool = False) -> bool:
    """
    Match an input message against procedural skill triggers and execute if matched.
    """
    from kit.skills.executor import execute_skill
    from kit.skills.matcher import match_trigger

    matches = match_trigger(message)
    if not matches:
        return False

    # v0.1: We only handle the first match or top match for simplicity
    # If multiple matches exist, we could prompt to choose, but v0.1 follows the keyword rule.
    match = matches[0]
    return execute_skill(match, dry_run=dry_run)


def run_procedural_skill(name: str, dry_run: bool = False) -> bool:
    """Directly execute a procedural skill by name."""
    from kit.skills.executor import execute_skill
    from kit.skills.matcher import list_procedural_skills

    skills = list_procedural_skills()
    target = next((s for s in skills if s.get("name") == name), None)

    if not target:
        print(f"[kit] ERROR: Procedural skill '{name}' not found.")
        return False

    return execute_skill(target, dry_run=dry_run)


if __name__ == "__main__":
    from kit.cli.main import main

    main()
