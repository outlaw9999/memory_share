# tests/test_v124_stress.py
# v1.2.4 FINAL STRESS TEST SUITE
# Chaos + Concurrency + IO + CLI Chain

import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def count_observations_by_node_uid(db_path, uid_pattern):
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM observations o JOIN nodes n ON o.node_id = n.id WHERE n.uid LIKE ? AND o.is_active = 1",
        (uid_pattern,),
    ).fetchone()[0]
    conn.close()
    return count


class TestCLIStress:
    @staticmethod
    def test_cli_chain_init_learn_recall():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "chain.db"
            for i in range(10):
                res = subprocess.run(
                    [sys.executable, "-m", "kit", "--db", str(db_path), "init"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                assert res.returncode == 0, f"Init failed cycle {i}: {res.stderr}"
                res = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "kit",
                        "--db",
                        str(db_path),
                        "learn",
                        "--uid",
                        f"fact_{i}",
                        "--content",
                        f"Cycle {i} fact",
                        "--tag",
                        "decision",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                assert res.returncode == 0, f"Learn failed cycle {i}: {res.stderr}"
                res = subprocess.run(
                    [sys.executable, "-m", "kit", "--db", str(db_path), "recall", f"fact_{i}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                assert res.returncode == 0, f"Recall failed cycle {i}: {res.stderr}"
                assert f"Cycle {i} fact" in res.stdout, f"Recall missing content cycle {i}"
            print("[PASS] CLI chain 10 cycles: init -> learn -> recall")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass

    @staticmethod
    def test_cli_idempotency_under_load():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "idem.db"
            subprocess.run([sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=10)
            for _ in range(20):
                res = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "kit",
                        "--db",
                        str(db_path),
                        "learn",
                        "--uid",
                        "same_fact",
                        "--content",
                        "Same content",
                        "--tag",
                        "decision",
                    ],
                    capture_output=True,
                    timeout=10,
                )
                assert res.returncode == 0, f"Learn failed: {res.stderr}"
            count = count_observations_by_node_uid(db_path, "same_fact")
            assert count == 1, f"Idempotency violated: {count} entries (expected 1)"
            print("[PASS] Idempotency under 20 rapid calls")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass


class TestConcurrencyStress:
    @staticmethod
    def test_parallel_learns():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "concurrent.db"
            subprocess.run([sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=10)
            errors = []
            success_count = [0]
            lock = threading.Lock()

            def learn_fact(i):
                try:
                    res = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "kit",
                            "--db",
                            str(db_path),
                            "learn",
                            "--uid",
                            f"parallel_{i}",
                            "--content",
                            f"Parallel fact {i}",
                            "--tag",
                            "decision",
                        ],
                        capture_output=True,
                        timeout=15,
                    )
                    with lock:
                        if res.returncode == 0:
                            success_count[0] += 1
                        else:
                            errors.append(f"Thread {i}: {res.stderr}")
                except Exception as e:
                    with lock:
                        errors.append(f"Thread {i} exception: {e}")

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(learn_fact, i) for i in range(10)]
                for _f in as_completed(futures):
                    pass

            assert len(errors) == 0, f"Parallel learns had errors: {errors}"
            assert success_count[0] == 10, f"Only {success_count[0]}/10 succeeded"
            count = count_observations_by_node_uid(db_path, "parallel_%")
            assert count == 10, f"DB inconsistent: {count} entries (expected 10)"
            print("[PASS] 10 parallel learns completed without corruption")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass

    @staticmethod
    def test_parallel_recalls():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "recall_parallel.db"
            subprocess.run([sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=10)
            for i in range(5):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "kit",
                        "--db",
                        str(db_path),
                        "learn",
                        "--uid",
                        f"fact_{i}",
                        "--content",
                        f"Fact {i}",
                        "--tag",
                        "decision",
                    ],
                    capture_output=True,
                    timeout=10,
                )

            def recall_fact(i):
                try:
                    res = subprocess.run(
                        [sys.executable, "-m", "kit", "--db", str(db_path), "recall", f"fact_{i}"],
                        capture_output=True,
                        timeout=10,
                    )
                    return res.returncode == 0
                except Exception:
                    return False

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(recall_fact, i % 5) for i in range(10)]
                results = [f.result() for f in as_completed(futures)]
            assert all(results), "Some parallel recalls failed or timed out"
            print("[PASS] 10 parallel recalls without deadlock")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass


class TestIOStress:
    @staticmethod
    def test_rapid_init_cycles():
        tmpdir = tempfile.mkdtemp()
        try:
            for i in range(50):
                cycle_dir = Path(tmpdir) / f"cycle_{i}"
                cycle_dir.mkdir()
                db_path = cycle_dir / "rapid.db"
                res = subprocess.run(
                    [sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=5
                )
                assert res.returncode == 0, f"Cycle {i} failed"
            dirs = list(Path(tmpdir).iterdir())
            assert len(dirs) == 50, f"Expected 50 dirs, got {len(dirs)}"
            print("[PASS] 50 rapid init cycles completed")
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def test_db_size_under_load():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "size_test.db"
            subprocess.run([sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=10)
            for i in range(100):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "kit",
                        "--db",
                        str(db_path),
                        "learn",
                        "--uid",
                        f"fact_{i}",
                        "--content",
                        f"Content for fact {i}" * 10,
                        "--tag",
                        "decision",
                    ],
                    capture_output=True,
                    timeout=10,
                )
            db_size = db_path.stat().st_size
            assert db_size < 1_000_000, f"DB size unexpected: {db_size} bytes"
            print(f"[PASS] DB size under load: {db_size} bytes (reasonable)")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass


class TestCrashRecovery:
    @staticmethod
    def test_interrupt_during_learn():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "interrupt.db"
            subprocess.run([sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=10)
            for i in range(5):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "kit",
                        "--db",
                        str(db_path),
                        "learn",
                        "--uid",
                        f"pre_{i}",
                        "--content",
                        f"Pre-interrupt {i}",
                        "--tag",
                        "decision",
                    ],
                    capture_output=True,
                    timeout=10,
                )
            pre_count = count_observations_by_node_uid(db_path, "pre_%")
            assert pre_count == 5, f"Pre-interrupt state wrong: {pre_count}"
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "kit",
                    "--db",
                    str(db_path),
                    "learn",
                    "--uid",
                    "interrupt_test",
                    "--content",
                    "This should not complete",
                    "--tag",
                    "decision",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.1)
            proc.terminate()
            proc.wait(timeout=5)
            interrupt_count = count_observations_by_node_uid(db_path, "interrupt_test")
            assert interrupt_count in [0, 1], f"Partial write detected: {interrupt_count}"
            print(f"[PASS] Interrupted learn: DB consistent (interrupt_test = {interrupt_count})")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass

    @staticmethod
    def test_wal_checkpoint_integrity():
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "wal_test.db"
            subprocess.run([sys.executable, "-m", "kit", "--db", str(db_path), "init"], capture_output=True, timeout=10)
            for i in range(10):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "kit",
                        "--db",
                        str(db_path),
                        "learn",
                        "--uid",
                        f"wal_{i}",
                        "--content",
                        f"WAL fact {i}",
                        "--tag",
                        "decision",
                    ],
                    capture_output=True,
                    timeout=10,
                )
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            count = count_observations_by_node_uid(db_path, "wal_%")
            assert count == 10, f"WAL checkpoint failed: {count}/10 facts"
            print(f"[PASS] WAL checkpoint integrity verified: {count}/10 facts")
        finally:
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass


if __name__ == "__main__":
    import traceback

    print("=" * 70)
    print("v1.2.4 FINAL STRESS TEST SUITE")
    print("=" * 70)

    test_suites = [
        (
            "CLI CHAIN STRESS",
            [
                TestCLIStress.test_cli_chain_init_learn_recall,
                TestCLIStress.test_cli_idempotency_under_load,
            ],
        ),
        (
            "CONCURRENCY STRESS",
            [
                TestConcurrencyStress.test_parallel_learns,
                TestConcurrencyStress.test_parallel_recalls,
            ],
        ),
        (
            "IO STRESS",
            [
                TestIOStress.test_rapid_init_cycles,
                TestIOStress.test_db_size_under_load,
            ],
        ),
        (
            "CRASH RECOVERY",
            [
                TestCrashRecovery.test_interrupt_during_learn,
                TestCrashRecovery.test_wal_checkpoint_integrity,
            ],
        ),
    ]

    total_passed = total_failed = 0

    for suite_name, tests in test_suites:
        print(f"\n[{suite_name}]")
        print("-" * 50)
        for test_func in tests:
            try:
                print(f"  Running {test_func.__name__}...", end=" ", flush=True)
                test_func()
                print("OK")
                total_passed += 1
            except AssertionError as e:
                print(f"FAIL: {e}")
                total_failed += 1
            except Exception as e:
                print(f"ERROR: {e}")
                traceback.print_exc()
                total_failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {total_passed} passed, {total_failed} failed")
    print("=" * 70)

    sys.exit(1 if total_failed > 0 else 0)
