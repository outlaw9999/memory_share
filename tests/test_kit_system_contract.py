# tests/test_kit_system_contract.py
# v1.2.5 — SYSTEM CONTRACT TEST (Core Chain TDD)
#
# This test validates the complete memory lifecycle under the CLI orchestration.
# TIER 0 critical path: kit init → kit learn → kit recall
#
# INVARIANT: All commands must comply with the Workspace Initialization Guard.

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def run_kit_command(cwd: Path, *args) -> tuple[int, str, str]:
    """
    Execute a kit command in a subprocess.

    Returns: (returncode, stdout, stderr)
    """
    # Get the repo root (parent of tests/)
    repo_root = Path(__file__).parent.parent.absolute()

    # Set environment for v1.2.5 Titanium enforcement bypass (internal lock only)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    env["KIT_BYPASS_RUNTIME_LOCK"] = "1"
    env["KIT_DISABLE_ASYNC_BAKE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["VANTAGE_HOME"] = os.path.join(str(repo_root), "non_existent_vantage")
    # 1.2.5ISOLATION: Use the temp directory as HOME to isolate global_brain.db
    env["USERPROFILE"] = str(cwd.parent)  # For Windows
    env["HOME"] = str(cwd.parent)  # For Unix-like

    cmd = [sys.executable, "-m", "kit"] + list(args)

    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120.0,
        env=env,
    )

    # v1.2.5: PROCESS LIFECYCLE BARRIER (Windows ONLY)
    # Ensure OS has released file handles before next command or cleanup
    if os.name == "nt":
        import time

        time.sleep(0.3)

    return result.returncode, result.stdout, result.stderr


class TestKitSystemContract:
    """TIER 0 — Memory lifecycle validation."""

    @staticmethod
    def test_core_chain_init_learn_recall():
        """
        CRITICAL PATH TEST:
        kit init → kit learn (add memory) → kit recall (retrieve)

        Validates:
        - init creates .kit directory and sentinel
        - learn writes to brain.db (positional content)
        - recall retrieves written memory
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Initialize project as git repo
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=5.0)

            # STEP 1: kit init
            print("[1] Testing: kit init")
            rc, stdout, stderr = run_kit_command(project_root, "init", "--force")
            assert rc == 0, f"kit init failed:\nstdout: {stdout}\nstderr: {stderr}"

            # Verify .kit directory was created
            kit_dir = project_root / ".kit"
            assert kit_dir.exists(), ".kit directory not created"
            assert (kit_dir / "local_brain.db").exists(), "local_brain.db not created"
            assert (kit_dir / "bootstrap_v1_2_5.seed").exists(), "sentinel file not created"
            print("[OK] kit init succeeded")

            # STEP 2: kit learn (Simplified UX: kit learn "text")
            print("[2] Testing: kit learn (simplified)")
            memory_content = "Test memory: pattern X observed 5 times"

            rc, stdout, stderr = run_kit_command(
                project_root,
                "learn",
                memory_content,
                "--tag",
                "pattern",
                "--uid",
                "test_pattern_x",
                "--importance",
                "0.8",
            )
            assert rc == 0, f"kit learn failed:\nstdout: {stdout}\nstderr: {stderr}"
            assert "OK" in stdout or "OK" in stderr, "Expected 'OK' on success"
            print("[OK] kit learn succeeded")

            # STEP 3: kit recall (retrieve the learned memory)
            print("[3] Testing: kit recall")
            rc, stdout, stderr = run_kit_command(project_root, "recall", "pattern")
            if rc != 0 or "test_pattern_x" not in stdout:
                print(f"DEBUG RECALL STDOUT: {stdout}")
                print(f"DEBUG RECALL STDERR: {stderr}")
            assert rc == 0, f"kit recall failed:\nstdout: {stdout}\nstderr: {stderr}"

            # The output of recall is normally a formatted table or text
            assert "test_pattern_x" in stdout, f"Symbol not found in recall output:\n{stdout}"
            assert "pattern X observed" in stdout, f"Content not found in recall output:\n{stdout}"
            print("[OK] kit recall retrieved memory")

            print("\n[PASS] Core Chain VERIFIED")
            if os.name == "nt":
                import time

                time.sleep(0.25)

    @staticmethod
    def test_init_guard_enforcement():
        """
        GOVERNANCE TEST:
        Verify that commands (except init/status) fail if workspace is not initialized.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            print("[1] Testing: kit recall without init (should fail)")
            rc, stdout, stderr = run_kit_command(project_root, "recall")

            assert rc == 1, "kit recall should fail without initialization"
            assert "Workspace not initialized" in stderr or "Workspace not initialized" in stdout
            print("[OK] Init guard blocked unauthorized recall")

            print("[2] Testing: kit learn without init (should fail)")
            rc, stdout, stderr = run_kit_command(project_root, "learn", "something")
            assert rc == 1, "kit learn should fail without initialization"
            print("[OK] Init guard blocked unauthorized learn")

            print("\n[PASS] Init Guard VERIFIED")
            if os.name == "nt":
                import time

                time.sleep(0.25)

    @staticmethod
    def test_memory_topology_local_isolation():
        """
        ISOLATION TEST:
        Ensure that local memory does not bleed between different workspaces.
        """
        with tempfile.TemporaryDirectory() as base_dir:
            base_path = Path(base_dir)
            ws1 = base_path / "ws1"
            ws2 = base_path / "ws2"
            ws1.mkdir()
            ws2.mkdir()

            # Init both
            rc1, out1, err1 = run_kit_command(ws1, "init")
            run_kit_command(ws1, "doctor")  # Force schema repair
            print(f"DEBUG: ws1 init out: {out1}\nerr: {err1}")
            rc2, out2, err2 = run_kit_command(ws2, "init")
            run_kit_command(ws2, "doctor")  # Force schema repair
            print(f"DEBUG: ws2 init out: {out2}\nerr: {err2}")

            print(f"DEBUG: ws1 content: {list(ws1.glob('**/*'))}")
            sentinel = ws1 / ".kit" / "bootstrap_v1_2_5.seed"
            print(f"DEBUG: ws1 sentinel exists: {sentinel.exists()} at {sentinel}")

            # Learn in WS1
            run_kit_command(ws1, "learn", "WS1 secret", "--uid", "secret_key")

            # Recall in WS1 (should find)
            rc, stdout, stderr = run_kit_command(ws1, "recall", "secret")
            if "WS1 secret" not in stdout:
                print(f"DEBUG ISOLATION WS1 STDOUT: {stdout}")
                print(f"DEBUG ISOLATION WS1 STDERR: {stderr}")
            assert "WS1 secret" in stdout

            # Recall in WS2 (should NOT find)
            rc, stdout, _ = run_kit_command(ws2, "recall", "secret")
            assert "WS1 secret" not in stdout

            print("\n[PASS] Memory topology isolation VERIFIED")
            if os.name == "nt":
                import time

                time.sleep(0.25)


if __name__ == "__main__":
    import traceback

    print("=" * 70)
    print("KIT v1.2.5 — SYSTEM CONTRACT TEST (Core Chain)")
    print("=" * 70 + "\n")

    test_suite = TestKitSystemContract()
    tests = [
        ("init -> learn -> recall", test_suite.test_core_chain_init_learn_recall),
        ("init guard enforcement", test_suite.test_init_guard_enforcement),
        ("LOCAL memory isolation", test_suite.test_memory_topology_local_isolation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print(f"\n[TEST] {test_name}")
            print("-" * 70)
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {test_name}")
            print(f"Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] {test_name}")
            print(f"Unexpected exception: {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
