import os
import shutil
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
    venv = get_venv_path()
    if venv:
        scripts_dir = venv / "Scripts"
        for name in ("kit-vantage.exe", "kit-vantage", "vantage.exe", "vantage"):
            bin_path = scripts_dir / name
            if bin_path.exists():
                return bin_path

    candidates = [
        os.getenv("VANTAGE_HOME"),
        venv,  # Check if .vantage is inside venv
        Path.cwd() / ".vantage",
        Path.home() / ".vantage",
    ]

    for cand in candidates:
        if not cand:
            continue
        base = Path(cand)
        for bin_path in (
            base / "target" / "release" / "vantage.exe",
            base / "target" / "release" / "vantage",
            base / "kit-vantage.exe",
            base / "kit-vantage",
            base / "vantage.exe",
            base / "vantage",
        ):
            if bin_path.exists():
                return bin_path

    for name in ("kit-vantage", "kit-vantage.exe", "vantage", "vantage.exe"):
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)

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
