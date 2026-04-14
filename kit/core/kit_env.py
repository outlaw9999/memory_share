import os
import sys
import sysconfig
from pathlib import Path

# --- Runtime Shield Invariants (v1.2.4-LOCK) ---
# This module acts as the Single Source of Truth for the environment.

def get_venv_path() -> Path | None:
    """Detect the project-local virtual environment (Root-only)."""
    # ECL v2: Strict Single-Source-of-Truth
    cwd = Path.cwd().resolve()
    # Find Repo Boundary (.git)
    root = None
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            root = parent
            break
            
    if root:
        venv = root / ".venv"
        if venv.is_dir():
            return venv
    return None

def is_env_locked() -> bool:
    """Verify if the current process is running from the project's .venv."""
    venv = get_venv_path()
    if not venv:
        return False
    # Smart Comparison: Check if sys.prefix is inside the discovered venv
    # This handles slight variations in path strings (UNC vs absolute)
    try:
        current_prefix = Path(sys.prefix).resolve()
        target_prefix = venv.resolve()
        return current_prefix == target_prefix
    except Exception:
        return False

def get_vantage_bin() -> Path | None:
    """Discover the Vantage binary with multi-anchor fallback."""
    candidates = [
        os.getenv("VANTAGE_HOME"),
        get_venv_path(), # Check if .vantage is inside venv
        Path.cwd() / ".vantage",
        Path.home() / ".vantage",
        r"E:\DEV\opensource_contrib\Vantage" # Legacy Fallback
    ]
    
    for cand in candidates:
        if not cand:
            continue
        base = Path(cand)
        # Check standard Rust target release location
        bin_path = base / "target" / "release" / "vantage.exe"
        if bin_path.exists():
            return bin_path
        # Check direct binary if base points to bin
        if base.name == "vantage.exe" and base.exists():
            return base
            
    return None

def get_substrate_report() -> dict:
    """Generate a forensic report of the current execution environment."""
    return {
        "interpreter": sys.executable,
        "prefix": sys.prefix,
        "is_locked": is_env_locked(),
        "venv_discovered": str(get_venv_path() or "missing"),
        "vantage_bin": str(get_vantage_bin() or "missing"),
        "data_path": sysconfig.get_path("data"),
    }
