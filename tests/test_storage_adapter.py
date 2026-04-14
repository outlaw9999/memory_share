import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.getcwd())

from kit.core.storage_adapter import (
    StorageAdapter,
    StorageConfig,
    InMemoryBuffer,
    StorageLockError,
)


def test_storage_adapter_init():
    """Test StorageAdapter initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        adapter = StorageAdapter.for_workspace(db_path)

        assert adapter.db_path == db_path
        assert adapter.config.wal_mode == True
        print("[PASS] StorageAdapter init")


def test_wal_mode_enabled():
    """Test WAL mode is enabled by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        adapter = StorageAdapter.for_workspace(db_path)

        conn = adapter.get_connection()
        result = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        assert result.upper() == "WAL"
        print("[PASS] WAL mode enabled")


def test_execute_with_retry():
    """Test execute with automatic retry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        adapter = StorageAdapter.for_workspace(db_path)

        adapter.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, data TEXT)")

        adapter.execute("INSERT INTO test (data) VALUES (?)", ("hello",))

        # v1.2.4-LOCK: read_one pruned, use read()
        results = adapter.read("SELECT * FROM test")

        assert len(results) > 0
        assert results[0]["data"] == "hello"
        print("[PASS] Execute with retry")


def test_memory_buffer():
    """Test in-memory buffer when disk is locked."""
    buffer = InMemoryBuffer(max_size=3)

    buffer.add({"sql": "test1", "params": ()})
    buffer.add({"sql": "test2", "params": ()})

    assert len(buffer) == 2

    ops = buffer.flush()
    assert len(ops) == 2
    assert buffer.is_empty()

    print("[PASS] Memory buffer")


def test_buffer_overflow():
    """Test buffer overflow removes oldest."""
    buffer = InMemoryBuffer(max_size=2)

    buffer.add({"sql": "a", "params": ()})
    buffer.add({"sql": "b", "params": ()})
    buffer.add({"sql": "c", "params": ()})

    assert len(buffer) == 2

    print("[PASS] Buffer overflow")


def test_config_customization():
    """Test custom configuration."""
    config = StorageConfig(
        wal_mode=False,
        max_retries=5,
        enable_memory_fallback=False,
    )

    adapter = StorageAdapter(Path("test.db"), config)

    assert adapter.config.wal_mode == False
    assert adapter.config.max_retries == 5
    assert adapter.config.enable_memory_fallback == False

    print("[PASS] Config customization")


if __name__ == "__main__":
    tests = [
        test_storage_adapter_init,
        test_wal_mode_enabled,
        test_execute_with_retry,
        test_memory_buffer,
        test_buffer_overflow,
        test_config_customization,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
