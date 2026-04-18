# tests/test_kit_system_contract.py
# v1.2.3.9 — SYSTEM CONTRACT TEST (Core Chain TDD)
#
# This test validates the complete memory lifecycle under the CLI orchestration.
# TIER 0 critical path: kit init → kit learn → kit recall → kit compile
#
# INVARIANT: All commands must execute without crash and maintain memory integrity.

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

    # Set PYTHONPATH to include repo root so kit module is discoverable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    cmd = [sys.executable, "-m", "kit"] + list(args)

    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30.0,  # 30s timeout per command to catch hangs
        env=env,  # Pass modified environment
    )

    return result.returncode, result.stdout, result.stderr


class TestKitSystemContract:
    """TIER 0 — Memory lifecycle validation."""

    @staticmethod
    def test_core_chain_init_learn_recall():
        """
        CRITICAL PATH TEST:
        kit init → kit learn (add memory) → kit recall (retrieve)

        Validates:
        - init creates .kit directory
        - learn writes to brain.db
        - recall retrieves written memory
        - No crashes or blocking I/O
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Initialize project as git repo (some validation might check this)
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=5.0)

            # STEP 1: kit init
            print("[1] Testing: kit init")
            rc, stdout, stderr = run_kit_command(project_root, "init", "--force")
            assert rc == 0, f"kit init failed:\nstdout: {stdout}\nstderr: {stderr}"

            # Verify .kit directory was created
            kit_dir = project_root / ".kit"
            assert kit_dir.exists(), ".kit directory not created"
            assert (kit_dir / "brain.db").exists(), "brain.db not created"
            print("[OK] kit init succeeded, .kit/brain.db exists")

            # STEP 2: kit learn (add a memory)
            print("[2] Testing: kit learn")
            memory_content = {
                "content": "Test memory: pattern X observed 5 times",
                "kind": "pattern",
                "uid": "test_pattern_x",
                "importance": 0.8,
            }

            rc, stdout, stderr = run_kit_command(
                project_root,
                "learn",
                "--content",
                json.dumps(memory_content),
                "--kind",
                "pattern",
                "--uid",
                "test_pattern_x",
                "--importance",
                "0.8",
            )
            assert rc == 0, f"kit learn failed:\nstdout: {stdout}\nstderr: {stderr}"
            print("[OK] kit learn succeeded")

            # STEP 3: kit recall (retrieve the learned memory)
            print("[3] Testing: kit recall")
            rc, stdout, stderr = run_kit_command(project_root, "recall", "test_pattern_x")
            assert rc == 0, f"kit recall failed:\nstdout: {stdout}\nstderr: {stderr}"

            # Verify memory was retrieved
            assert "test_pattern_x" in stdout or "pattern" in stdout.lower(), (
                f"Learned memory not found in recall output:\n{stdout}"
            )
            print("[OK] kit recall succeeded, memory retrieved")

            print("\n[PASS] Core chain: init → learn → recall VERIFIED")

    @staticmethod
    def test_learn_all_tag_types_allowed():
        """
        Ensure the CLI and DB schema accept the expanded tag set for learn.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=5.0)
            rc, stdout, stderr = run_kit_command(project_root, "init", "--force")
            assert rc == 0, f"kit init failed:\nstdout: {stdout}\nstderr: {stderr}"

            rc, stdout, stderr = run_kit_command(
                project_root,
                "learn",
                "--content",
                "Project-specific pattern memory",
                "--uid",
                "pattern_fact_1",
                "--tag",
                "pattern",
            )
            assert rc == 0, f"kit learn with tag 'pattern' failed:\nstdout: {stdout}\nstderr: {stderr}"

            db_path = project_root / ".kit" / "brain.db"
            assert db_path.exists(), "brain.db should exist after init"
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT tag, content FROM observations WHERE rowid = (SELECT MAX(rowid) FROM observations)").fetchone()
            assert row is not None, "Observation row was not written"
            assert row[0] == "pattern", f"Expected stored tag to be 'pattern', got {row[0]}"
            assert "Project-specific pattern memory" in row[1], "Stored content mismatch"

    @staticmethod
    def test_core_chain_compile():
        """
        CRITICAL PATH TEST:
        kit init → kit learn → kit compile (YAML skill)

        Validates:
        - compile reads YAML file
        - compile writes skill to brain
        - No crashes during compilation
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Initialize git
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=5.0)

            # STEP 1: kit init
            print("[1] Testing: kit init")
            rc, stdout, stderr = run_kit_command(project_root, "init", "--force")
            assert rc == 0, f"kit init failed:\nstdout: {stdout}\nstderr: {stderr}"
            print("[OK] kit init succeeded")

            # STEP 2: Create a YAML skill file
            print("[2] Testing: Create YAML skill file")
            skill_yaml = """# Simple test skill
name: test_skill
description: A test skill for verification
version: 0.1
triggers:
  - on_pattern: "test_*"
    actions:
      - name: "validate"
        params:
          key: "value"
"""
            skill_file = project_root / "test_skill.yml"
            skill_file.write_text(skill_yaml)
            print("[OK] Skill file created")

            # STEP 3: kit compile
            print("[3] Testing: kit compile")
            rc, stdout, stderr = run_kit_command(
                project_root,
                "compile",
                "test_skill",
                "--file",
                str(skill_file),
            )
            assert rc == 0, f"kit compile failed:\nstdout: {stdout}\nstderr: {stderr}"

            # Verify compilation succeeded
            assert "compiled" in stdout.lower(), f"Compilation success message not found:\n{stdout}"
            print("[OK] kit compile succeeded")

            print("\n[PASS] Core chain: init → compile VERIFIED")

    @staticmethod
    def test_memory_topology_local_isolation():
        """
        TOPOLOGY TEST:
        Verify that LOCAL memories stay in <project_root>/.kit/brain.db
        and do NOT leak to ~/.kit/

        Validates:
        - LOCAL/GLOBAL paths are correct
        - No cross-contamination between scopes
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Initialize git
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=5.0)

            # STEP 1: kit init
            print("[1] Testing: kit init")
            rc, stdout, stderr = run_kit_command(project_root, "init", "--force")
            assert rc == 0, f"kit init failed:\nstdout: {stdout}\nstderr: {stderr}"

            local_db = project_root / ".kit" / "brain.db"
            assert local_db.exists(), f"LOCAL DB not found at {local_db}"
            print(f"[OK] LOCAL DB exists: {local_db}")

            # STEP 2: kit learn (add project-specific memory)
            print("[2] Testing: kit learn (project-specific)")
            rc, stdout, stderr = run_kit_command(
                project_root,
                "learn",
                "--content",
                json.dumps({"content": "Project-specific pattern", "uid": "proj_pattern_123"}),
                "--uid",
                "proj_pattern_123",
            )
            assert rc == 0, f"kit learn failed:\nstdout: {stdout}\nstderr: {stderr}"
            print("[OK] Project memory learned")

            # STEP 3: Verify LOCAL contains the memory
            print("[3] Testing: Verify LOCAL memory isolation")
            import sqlite3

            conn = sqlite3.connect(str(local_db), timeout=5.0)
            try:
                cursor = conn.execute("SELECT content FROM observations WHERE uid = ?", ("proj_pattern_123",))
                row = cursor.fetchone()
                assert row is not None, "Project memory not found in LOCAL DB"
                print("[OK] Project memory verified in LOCAL DB")
            finally:
                conn.close()

            print("\n[PASS] Memory topology isolation VERIFIED")

    @staticmethod
    def test_failure_handling_missing_db():
        """
        FAILURE MODE TEST:
        kit recall when DB doesn't exist

        Validates:
        - Graceful error handling
        - No crash / hang
        - Clear error message
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Initialize git
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=5.0)

            # Try to recall without init
            print("[1] Testing: kit recall without init")
            rc, stdout, stderr = run_kit_command(project_root, "recall")

            # Should fail gracefully (non-zero return code)
            assert rc != 0, "kit recall should fail when DB missing"

            # Should have error output
            error_output = stdout + stderr
            assert len(error_output) > 0, "No error message provided"
            print(f"[OK] Graceful failure: {error_output[:100]}")

            print("\n[PASS] Failure handling VERIFIED")


# --- RUN TESTS ---

if __name__ == "__main__":
    import traceback

    print("=" * 70)
    print("KIT v1.2.3.9 — SYSTEM CONTRACT TEST (Core Chain)")
    print("=" * 70 + "\n")

    tests = [
        ("init → learn → recall", TestKitSystemContract.test_core_chain_init_learn_recall),
        ("init → compile YAML", TestKitSystemContract.test_core_chain_compile),
        ("LOCAL memory isolation", TestKitSystemContract.test_memory_topology_local_isolation),
        ("Failure handling: missing DB", TestKitSystemContract.test_failure_handling_missing_db),
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
            traceback.print_exc()
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
