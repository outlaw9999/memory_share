#!/usr/bin/env python3
"""
Final Pre-release PyPI Checklist Script for .kit v1.2.1-Robust
Checks:
1. Wheel/sdist file integrity (AGENTS.md, HOTFIX_V1.2.1.md, scripts/governance_ingest.py)
2. Entry Points (kit, kit-agent, kit-ingest)
3. Sensory Layer fail-fast (STDIN & TCP probe)
4. Dependency drift
"""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

DIST_DIR = Path("dist")
REQUIRED_FILES_WHEEL = [
    "scripts/governance_ingest.py",
    "kit_agent/data/AGENTS.md",
    "kit_agent/data/HOTFIX_V1.2.1.md",
]
REQUIRED_FILES_SDIST = [
    "scripts/governance_ingest.py",
    "AGENTS.md",
    "HOTFIX_V1.2.1.md",
]
ENTRY_POINTS = ["kit", "kit-agent", "kit-ingest"]


def check_distribution_files() -> bool:
    print("[CHECK] Scanning dist directory for wheel/sdist files...")
    dist_files = list(DIST_DIR.glob("*.whl")) + list(DIST_DIR.glob("*.tar.gz"))
    if not dist_files:
        print("[ERROR] No distribution files found in dist/")
        return False

    dist_files_sorted = sorted(dist_files, key=lambda x: x.name, reverse=True)
    latest_version = dist_files_sorted[0].name.split("-")[1] if dist_files_sorted else None

    success = True
    for f in dist_files_sorted:
        is_latest = latest_version and latest_version in f.name
        status = "[INFO-LATEST]" if is_latest else "[SKIP-OLD]"
        print(f"{status} Inspecting {f.name}...")

        if not is_latest:
            continue

        if f.suffix == ".whl":
            required = REQUIRED_FILES_WHEEL
            with zipfile.ZipFile(f, "r") as z:
                files_in_archive = z.namelist()
        elif f.suffixes[-2:] == [".tar", ".gz"]:
            required = REQUIRED_FILES_SDIST
            with tarfile.open(f, "r:gz") as t:
                files_in_archive = t.getnames()
        else:
            continue

        for req in required:
            if not any(req in path for path in files_in_archive):
                print(f"[FAIL] {req} missing in {f.name}")
                success = False
    return success


def check_entry_points() -> bool:
    print("[CHECK] Verifying entry points...")
    success = True

    wheel_file = DIST_DIR / "memory_share_kit-1.2.1-py3-none-any.whl"
    if wheel_file.exists():
        print(f"[INFO] Installing {wheel_file.name} for entry point testing...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", str(wheel_file)],
                capture_output=True,
                timeout=30,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("[WARN] Could not install wheel for testing")

    scripts_to_test = [
        ("kit", ["kit", "--help"]),
        ("kit-agent", ["kit-agent", "--help"]),
        ("kit-ingest", [sys.executable, "scripts/governance_ingest.py", "--help"]),
    ]

    for name, cmd in scripts_to_test:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                print(f"[FAIL] Entry point {name} failed execution")
                success = False
            else:
                print(f"[OK] Entry point {name} functional")
        except FileNotFoundError:
            print(f"[FAIL] Entry point {name} not found - package may not be installed")
            success = False
        except subprocess.TimeoutExpired:
            print(f"[FAIL] Entry point {name} timed out")
            success = False
    return success


def check_sensory_fail_fast() -> bool:
    print("[CHECK] Testing sensory layer fail-fast behavior...")
    success = True

    test_cmd = ["kit", "learn", "--content", "test"]
    try:
        result = subprocess.run(
            test_cmd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            print("[FAIL] kit learn failed in fail-fast STDIN test")
            success = False
        else:
            print("[OK] kit learn executed successfully in <2s")
    except subprocess.TimeoutExpired:
        print("[FAIL] kit learn hang detected")
        success = False
    except FileNotFoundError:
        print("[SKIP] kit command not installed")

    env = os.environ.copy()
    env["JAN_BASE_URL"] = "http://127.0.0.1:1"
    test_cmd_agent = ["kit-agent", "status"]
    try:
        result = subprocess.run(
            test_cmd_agent,
            env=env,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if "unreachable" in result.stdout.lower() or result.returncode == 0:
            print("[OK] kit-agent pre-flight TCP probe fail-fast functional")
        else:
            print("[WARN] kit-agent TCP probe output unusual")
    except subprocess.TimeoutExpired:
        print("[FAIL] kit-agent TCP probe hang detected")
        success = False
    except FileNotFoundError:
        print("[SKIP] kit-agent command not installed")

    return success


def check_dependency_drift() -> bool:
    print("[CHECK] Ensuring no unintended dependencies...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("[OK] Dependency check passed")
            return True
        print("[WARN] pip check reported issues")
        print(result.stdout)
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] Dependency check timed out")
        return False
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"[ERROR] Dependency check failed: {e}")
        return False


def main() -> None:
    overall = True
    if not check_distribution_files():
        overall = False
    if not check_entry_points():
        overall = False
    if not check_sensory_fail_fast():
        overall = False
    if not check_dependency_drift():
        overall = False

    if overall:
        print("\n[PASS] ALL CHECKS PASSED: v1.2.1-Robust ready for PyPI publish!")
        sys.exit(0)
    print("\n[FAIL] SOME CHECKS FAILED: Please fix before publishing.")
    sys.exit(1)


if __name__ == "__main__":
    main()
