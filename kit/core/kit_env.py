import os
import shutil
import sys
import sysconfig
from enum import StrEnum
from pathlib import Path

# --- Runtime Shield Invariants (v1.2.4-LOCK) ---

class ExecutionMode(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"

def get_execution_mode() -> ExecutionMode:
    """Detect the current execution mode (v1.2.4-TITANIUM)."""
    # 1. Environment variable override
    mode_env = os.getenv("KIT_RUNTIME_MODE", "").lower()
    if mode_env in [m.value for m in ExecutionMode]:
        return ExecutionMode(mode_env)
    
    # 2. Pytest detection
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return ExecutionMode.TEST
    
    # 3. Default to development (or production if packaged)
    return ExecutionMode.DEVELOPMENT

def get_venv_path() -> Path | None:
    """Detect the project-local virtual environment (Root-only)."""
    # ECL v2: Strict Single-Source-of-Truth
    cwd = Path.cwd().resolve()
    # Find Repo Boundary (.git)
    root = None
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists() or (parent / ".kit-root").exists():
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
    """Discover the Vantage binary with multi-anchor fallback (v1.2.4-TITANIUM)."""
    # 1. Environment Variable Override (Highest Priority)
    env_home = os.getenv("VANTAGE_HOME")
    if env_home:
        base = Path(env_home)
        for name in ("kit-vantage.exe", "kit-vantage", "vantage.exe", "vantage"):
            # Check root and target/release
            paths = [base / name, base / "target" / "release" / name]
            for p in paths:
                if p.exists():
                    return p

    # 2. Local Repo Check (.vantage or kit-vantage in root)
    cwd = Path.cwd()
    for name in ("kit-vantage.exe", "kit-vantage"):
        local_bin = cwd / name
        if local_bin.exists():
            return local_bin

    # 3. Virtual Environment Check (.venv/Scripts)
    # NOTE: This might be the shim. We check if it's the real binary (size > 1MB) 
    # or if we should keep looking for a "real" one.
    venv = get_venv_path()
    if venv:
        scripts_dir = venv / "Scripts" if sys.platform == "win32" else venv / "bin"
        for name in ("kit-vantage.exe", "kit-vantage", "vantage.exe", "vantage"):
            bin_path = scripts_dir / name
            if bin_path.exists():
                # If it's very small, it's likely a shim or script wrapper
                if bin_path.stat().st_size > 1_000_000:
                    return bin_path
                # Keep it as a backup candidate
                pass

    # 4. Sibling Repository Check (ECL v2 Standard)
    # If we are in e:/DEV/opensource_contrib/memory_share_kit
    # We check e:/DEV/opensource_contrib/Vantage
    try:
        repo_root = None
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                repo_root = parent
                break
        
        if repo_root:
            sibling_vantage = repo_root.parent / "Vantage"
            if sibling_vantage.is_dir():
                for name in ("kit-vantage.exe", "kit-vantage"):
                    # Check root and target/release
                    paths = [
                        sibling_vantage / name, 
                        sibling_vantage / "target" / "release" / name,
                        sibling_vantage / "target" / "release" / "vantage.exe"
                    ]
                    for p in paths:
                        if p.exists():
                            return p
    except Exception:
        pass

    # 5. System PATH
    for name in ("kit-vantage", "kit-vantage.exe", "vantage", "vantage.exe"):
        resolved = shutil.which(name)
        if resolved:
            res_path = Path(resolved)
            # Avoid returning the shim if we are already in the venv
            if venv and scripts_dir in res_path.parents:
                if res_path.stat().st_size < 100_000: # Likely shim
                    continue
            return res_path

    # 6. Final Fallback to Shim in venv
    if venv:
        for name in ("kit-vantage.exe", "kit-vantage"):
            bin_path = scripts_dir / name
            if bin_path.exists():
                return bin_path

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
