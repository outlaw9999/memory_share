from kit.skills.executor import execute_skill as run_skill

def watch(poll_interval: float = 0.2):
    """Runtime: Stream semantic memory events."""
    from kit.api import get_brain
    return get_brain().stream_events(poll_interval)

def where() -> str:
    """Runtime: Get current workspace identity."""
    from kit.api import get_brain
    return get_brain().get_workspace_id()

__all__ = ["run_skill", "watch", "where"]
