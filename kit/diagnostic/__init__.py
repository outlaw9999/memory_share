from kit.cli.doctor import run_doctor as doctor
from kit.core.kit_cognitive_core import SAMBrain
from kit.core.repo_scanner import scan_repo as scan
from kit.core.kit_hygiene import generate_hygiene_report as stats

def blame(symbol: str) -> list:
    """Diagnostic: Retrieve causality chain for a symbol."""
    from kit.api import get_brain
    return get_brain().get_blame(symbol)

def status() -> str:
    """Diagnostic: Get system health status."""
    from kit.api import get_brain
    brain = get_brain()
    # Simple status logic
    return "HEALTHY" if brain.db_path.exists() else "EMPTY"

__all__ = ["doctor", "blame", "scan", "stats", "status"]
