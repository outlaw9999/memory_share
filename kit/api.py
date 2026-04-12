import os
import uuid
from pathlib import Path
from typing import Any

from kit.core.kit_cognitive_core import RankingAssessment, SAMBrain, SAMBrainError

# --- Stable API Boundary Definitions ---
# This file is the primary entry point for community forks and IDE integrations.

_brain_instance: SAMBrain | None = None


def resolve_paths(force_local: bool = False, mode: str = "auto") -> tuple[Path, Path, Path]:
    """
    Standard Path Resolver for .kit Kernel.
    Modes:
      - 'auto': Parent-walk up to .git boundary to find .kit (default)
      - 'isolated': Force create .kit in CWD, ignore parents (used for tests/sub-projects)
    """
    kit_home = os.getenv("KIT_HOME")
    if kit_home:
        global_path = Path(kit_home).expanduser().resolve()
    else:
        global_path = (Path.home() / ".kit").resolve()

    global_db = global_path / "global.db"
    global_path.mkdir(parents=True, exist_ok=True)

    cwd = Path.cwd().resolve()

    # --- STRATEGY 1: EXPLICIT ISOLATION ---
    if force_local or mode == "isolated":
        project_db = cwd / ".kit" / "brain.db"
        (cwd / ".kit").mkdir(parents=True, exist_ok=True)
        return global_db, project_db, cwd

    # --- STRATEGY 2: AUTO DISCOVERY (Boundary-Aware) ---
    project_db = None
    root_path = cwd

    # !!! Step 1: Find Repo Boundary (.git)
    repo_root = None
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            repo_root = parent
            break

    # !!! Step 2: Walk parent tree but STOP at repo boundary
    for parent in [cwd] + list(cwd.parents):
        # PRIORITY 1: Existing brain database (Marker of an active project)
        if (parent / ".kit" / "brain.db").exists():
            root_path = parent
            project_db = parent / ".kit" / "brain.db"
            break
        # PRIORITY 2: .kit marker directory (Newly initialized project)
        if (parent / ".kit").is_dir():
            root_path = parent
            project_db = parent / ".kit" / "brain.db"
            break

        # Boundary Lock: Never cross out of the nearest .git into a parent project
        if repo_root and parent == repo_root:
            break

    # ZERO FALLBACK: If no .kit found within boundary, enforce isolation.
    if project_db is None:
        (cwd / ".kit").mkdir(parents=True, exist_ok=True)
        project_db = cwd / ".kit" / "brain.db"
        root_path = cwd
        # Signal creation
        print(f"[kit] Initialized isolated brain at {root_path}")

    return global_db, project_db, root_path


# @epistemic: init_kernel
def init_kernel(db_path: Path | None = None, mode: str = "auto") -> None:
    """Initialize the global SAMBrain instance."""
    global _brain_instance
    global_db, project_db, root_path = resolve_paths(mode=mode)
    target_project_db = db_path if db_path else project_db
    _brain_instance = SAMBrain(target_project_db, root_path=root_path)
    _brain_instance.attach_global(global_db)


def get_brain() -> SAMBrain:
    """Get the initialized SAMBrain instance."""
    if _brain_instance is None:
        init_kernel()
    assert _brain_instance is not None
    return _brain_instance


# @epistemic: learn
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
    """Learn a fact with optional symbol anchoring and cognitive metadata."""
    meta = {"source": "cli", "actor": "human", "agent": "antigravity"}
    if metadata:
        meta.update(metadata)

    resolved_uid = uid if uid else str(uuid.uuid4())

    return get_brain().learn(
        uid=resolved_uid,
        content=content,
        tag=tag,
        kind=kind,
        importance=importance,
        layer=layer,
        namespace=namespace,
        agent_id=agent_id,
        to_global=to_global,
        supersede_id=supersede_id,
        scope=scope,
        metadata=meta,
        symbol=symbol,
        structural_hash=structural_hash,
        skip_render=skip_render,
    )


# @epistemic: search
def search(
    query: str, limit: int = 15, at: str | None = None, agent_id: str | None = None, fast: bool = False
) -> list[Any]:
    """Hybrid FTS Search."""
    return get_brain().search(query, limit, at_timestamp=at, agent_id=agent_id, fast=fast)


# @epistemic: recall
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
) -> list[Any]:
    """Ranked recall context awareness."""
    return get_brain().recall(
        entities,
        limit,
        at=at,
        agent_id=agent_id,
        here=here,
        symbol=symbol,
        query=query,
        with_global=with_global,
        fast=fast,
    )


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


def export_prompt(entities: list[str], limit: int = 10, budget: int = 1000) -> str:
    """Renders memory for LLM."""
    return get_brain().export_for_prompt(entities, limit, budget)


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


# @epistemic: preflight_check
def preflight_check(commit_msg: str, strict: bool = False, diff_text: str | None = None) -> dict[str, Any]:
    """Run cognitive governance preflight checks."""
    import dataclasses

    from kit.core.kit_governance import run_preflight

    result = run_preflight(commit_msg=commit_msg, brain=get_brain(), strict_mode=strict, diff_text=diff_text)
    return dataclasses.asdict(result)


# @epistemic: reflect_check
def reflect_check(diff_text: str | None = None, scope: str | None = None) -> dict[str, Any]:
    """Run cognitive reflection check."""
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

    report = run_reflect(get_brain(), diff_text, scope=scope)

    # Map ReflectReport fields to the list-of-issues format the CLI likes
    issues: list[dict[str, str]] = []
    for g in report.gaps:
        issues.append(
            {"type": "gap", "message": f"'{g}' not found in memory (New signal)", "suggestion": f"kit learn --uid {g}"}
        )
    for d in report.drifts:
        issues.append(
            {
                "type": "drift",
                "message": f"'{d}' found but not verified in this scope",
                "suggestion": f"kit learn --uid {d} --scope {scope or 'here'}",
            }
        )
    for v in report.violations:
        issues.append(
            {
                "type": "violation",
                "message": f"'{v}' violates an architectural invariant",
                "suggestion": f"kit blame {v}",
            }
        )

    matched_signals = report.confirmations + report.drifts + report.violations

    return {
        "score": report.score,
        "status": report.status,
        "issues": issues,
        "matched_signals": matched_signals,
        "suggestions": report.suggestions,
    }


def reflect(diff_text: str, scope: str | None = None) -> Any:
    """Run cognitive reflection on a code diff."""
    from kit.core.kit_reflect import run_reflect

    return run_reflect(get_brain(), diff_text, scope)


if __name__ == "__main__":
    from kit.cli.main import main

    main()
