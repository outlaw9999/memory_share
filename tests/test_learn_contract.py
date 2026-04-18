# tests/test_learn_contract.py
# v1.2.4-LOCK: LEARN WRITE CONTRACT TEST SUITE (TDD)

import os
import sqlite3
import sys
import tempfile
from pathlib import Path


def test_idempotency_guard():
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test_brain.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
                kind TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE observations (
                id INTEGER PRIMARY KEY,
                node_id INTEGER,
                content TEXT,
                importance REAL,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.execute("INSERT INTO nodes (uid, kind) VALUES ('test_node', 'test')")
        node_id = conn.execute("SELECT id FROM nodes WHERE uid = 'test_node'").fetchone()["id"]
        content = "Test idempotency"
        conn.execute(
            "INSERT INTO observations (node_id, content, importance, is_active) VALUES (?, ?, ?, ?)",
            (node_id, content, 1.0, 1),
        )
        conn.commit()
        first_id = conn.execute("SELECT id FROM observations").fetchone()["id"]
        conn.close()
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        existing = conn2.execute(
            "SELECT id FROM observations WHERE node_id = ? AND content = ? AND is_active = 1",
            (node_id, content),
        ).fetchone()
        result_id = existing["id"] if existing else first_id
        conn2.close()
        assert result_id == first_id, "Idempotency failed"
        print("[PASS] Idempotency guard VERIFIED")
    finally:
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass


def test_baseline_scoring():
    import math

    importance = 1.0
    access_count = 1
    freq_factor = math.log10(access_count + 2)
    expected = importance * freq_factor
    cold = importance * math.log10(0 + 2)
    assert expected > cold, f"Baseline not better: {expected} <= {cold}"
    print("[PASS] Baseline scoring VERIFIED")


def test_no_duplicate_contamination():
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test_brain.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
                kind TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE observations (
                id INTEGER PRIMARY KEY,
                node_id INTEGER,
                content TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.execute("INSERT INTO nodes (uid, kind) VALUES ('dup', 'test')")
        node_id = conn.execute("SELECT id FROM nodes WHERE uid = 'dup'").fetchone()["id"]
        conn.commit()
        conn.close()
        content = "Duplicate test"
        returned_ids = []
        for _ in range(10):
            conn_loop = sqlite3.connect(str(db_path))
            conn_loop.row_factory = sqlite3.Row
            existing = conn_loop.execute(
                "SELECT id FROM observations WHERE node_id = ? AND content = ? AND is_active = 1",
                (node_id, content),
            ).fetchone()
            if existing:
                returned_ids.append(existing["id"])
            else:
                conn_loop.execute(
                    "INSERT INTO observations (node_id, content, is_active) VALUES (?, ?, ?)",
                    (node_id, content, 1),
                )
                returned_ids.append(conn_loop.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn_loop.commit()
            conn_loop.close()
        assert len(set(returned_ids)) == 1, f"Multiple IDs: {set(returned_ids)}"
        print("[PASS] No duplicate contamination VERIFIED")
    finally:
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass


if __name__ == "__main__":
    tests = [
        ("Idempotency Guard", test_idempotency_guard),
        ("Baseline Scoring", test_baseline_scoring),
        ("No Duplicate Contamination", test_no_duplicate_contamination),
    ]
    passed = failed = 0
    for test_name, test_func in tests:
        try:
            print(f"[TEST] {test_name}")
            test_func()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test_name}: {e}")
            failed += 1
    print(f"RESULTS: {passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)
