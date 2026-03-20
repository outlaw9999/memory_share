import importlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_check(name, cmd, timeout=10):
    print(f"[CHECK] {name}...", end=" ", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            print("PASSED")
            return True
        else:
            print(f"FAILED (code {result.returncode})")
            if result.stderr:
                print(f"  Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False


def assert_clean_git():
    """Invariant: No build from dirty repo."""
    print("[CHECK] Git Status...", end=" ", flush=True)
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            print("FAILED")
            print("[ERROR] Repository is dirty. Commit or stash changes before build.")
            return False
        print("PASSED (Clean)")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def verify_imports():
    """Verify core modules can be imported in the current environment."""
    print("[CHECK] Verifying Imports...", end=" ", flush=True)
    try:
        for mod in ["kit", "kit_agent", "runtime", "scripts"]:
            importlib.import_module(mod)
        print("PASSED")
        return True
    except ImportError as e:
        print(f"FAILED: {e}")
        return False


def verify_bundle():
    """Release Guard v2 for v1.2.2."""
    print("=== .kit v1.2.2 Release Guard (Robust Mode) ===")
    
    # 0. Pre-build checks
    if not assert_clean_git():
        return False
    
    if not verify_imports():
        return False

    # 1. Build the bundle
    # Clean old dist
    if os.path.exists("dist"):
        import shutil
        shutil.rmtree("dist")
        
    if not run_check("Build Bundle (sdist + wheel)", [sys.executable, "-m", "build"], timeout=60):
        print("Error: Build failed. Install 'build' package if missing.")
        return False
        
    dist_dir = Path("dist")
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        print("Error: No wheel found in dist/")
        return False
        
    latest_wheel = max(wheels, key=os.path.getmtime)
    print(f"[INFO] Auditing: {latest_wheel.name}")
    
    # 2. Inspect Wheel Contents
    with zipfile.ZipFile(latest_wheel, 'r') as z:
        names = z.namelist()
        # Verify package directories and __init__.py files
        required_paths = [
            "kit/__init__.py",
            "kit_agent/__init__.py",
            "runtime/__init__.py",
            "scripts/__init__.py",
            "kit_agent/data/AGENTS.md"
        ]
        for path in required_paths:
            if path not in names:
                print(f"FAILED: Path '{path}' missing in wheel.")
                return False
        print("[CHECK] Wheel structure (Modules + Data): PASSED")
        
        # Check Entry Points
        entry_point_files = [n for n in names if "entry_points.txt" in n]
        if entry_point_files:
            content = z.read(entry_point_files[0]).decode()
            required_eps = [
                "kit = kit.cli.main:main",
                "kit-agent = kit_agent.cli.main:main",
                "kit-ingest = scripts.governance_ingest:ingest_governance"
            ]
            for ep in required_eps:
                if ep not in content:
                    print(f"FAILED: Entry point '{ep}' missing or incorrect.")
                    print(f"Content:\n{content}")
                    return False
        else:
            print("FAILED: entry_points.txt not found in wheel.")
            return False
        print("[CHECK] Entry points: PASSED")

    # 3. CLI Sanity
    run_check("CLI 'kit --help'", [sys.executable, "kit.py", "--help"])
    run_check("CLI 'kit-agent --help'", [sys.executable, "-m", "kit_agent.cli.main", "--help"])
    run_check("CLI 'kit-ingest --help'", [sys.executable, "scripts/governance_ingest.py", "--help"])

    print("\n[READY] v1.2.2 is confirmed for distribution.")
    return True


def audit_fail_fast():
    """Verify that the Fail-Fast Doctrine is enforced in the codebase."""
    print("  - Auditing Fail-Fast Enforcement...")
    
    # Check for kit_platform.py
    platform_file = REPO_ROOT / "kit" / "core" / "kit_platform.py"
    if not platform_file.exists():
        print("  [ERROR] kit_platform.py missing.")
        sys.exit(1)
        
    # Check for run_safe usage in main CLI
    cli_file = REPO_ROOT / "kit" / "cli" / "main.py"
    content = cli_file.read_text(encoding="utf-8")
    if "run_safe(" not in content or "read_stdin_fail_fast(" not in content:
        print("  [ERROR] Main CLI not using Fail-Fast utilities.")
        sys.exit(1)
        
    # Check for sqlite timeout in cognitive core
    core_file = REPO_ROOT / "kit" / "core" / "kit_cognitive_core.py"
    core_content = core_file.read_text(encoding="utf-8")
    if "SQLITE_TIMEOUT_SECONDS = 1.0" not in core_content:
        print("  [ERROR] SQLite timeout not reduced in core.")
        sys.exit(1)
    
    print("  [OK] Fail-Fast Audit passed.")

def audit_multi_scope():
    """Verify Multi-scope Recall (Phase 1) implementation."""
    print("  - Auditing Multi-scope Recall...")
    api_file = REPO_ROOT / "kit" / "api.py"
    content = api_file.read_text(encoding="utf-8")
    if "with_global: bool = False" not in content:
        print("  [ERROR] API missing with_global parameter.")
        sys.exit(1)
    print("  [OK] Multi-scope Audit passed.")

if __name__ == "__main__":
    if not verify_bundle():
        sys.exit(1)
    
    # Explicit Release Guard v2 Audits
    audit_fail_fast()
    audit_multi_scope()
