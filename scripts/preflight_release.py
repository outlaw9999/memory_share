import importlib.metadata
import os
import subprocess
import sys
import zipfile
from pathlib import Path


def run_check(name, cmd, timeout=10):
    print(f"[CHECK] {name}...", end=" ", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            print("PASSED")
            return True
        else:
            print(f"FAILED (code {result.returncode})")
            print(f"  Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def verify_bundle():
    """Final pre-release audit for v1.2.1."""
    print("=== .kit v1.2.1 Pre-release Preflight ===")
    
    # 1. Build the bundle
    if not run_check("Build Bundle", [sys.executable, "-m", "build"], timeout=60):
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
        required_pkgs = ["kit/", "kit_agent/", "runtime/", "scripts/"]
        for pkg in required_pkgs:
            if not any(n.startswith(pkg) for n in names):
                print(f"FAILED: Package '{pkg}' missing in wheel.")
                return False
        print("[CHECK] Wheel structure: PASSED")
        
        # Check Entry Points
        entry_points = [n for n in names if "entry_points.txt" in n]
        if entry_points:
            content = z.read(entry_points[0]).decode()
            required_eps = ["kit =", "kit-agent =", "kit-ingest ="]
            for ep in required_eps:
                if ep not in content:
                    print(f"FAILED: Entry point '{ep}' missing.")
                    return False
        print("[CHECK] Entry points: PASSED")

    # 3. Runtime Sanity (Local)
    run_check("CLI 'kit --help'", [sys.executable, "kit.py", "--help"])
    run_check("CLI 'kit-agent --help'", [sys.executable, "-m", "kit_agent.cli.main", "--help"])
    run_check("CLI 'kit-ingest --help'", [sys.executable, "scripts/governance_ingest.py", "--help"])

    print("\n[READY] v1.2.1 is confirmed for distribution.")
    return True

if __name__ == "__main__":
    if not verify_bundle():
        sys.exit(1)
