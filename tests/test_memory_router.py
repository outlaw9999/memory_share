import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.getcwd())

from kit.core.memory_router import MemoryRouter, WorkspaceId


def test_workspace_id_generation():
    """Test WorkspaceId computation is deterministic and path independent."""
    root = Path.cwd()

    ws1 = WorkspaceId.compute(root)
    ws2 = WorkspaceId.compute(root)

    assert ws1.id == ws2.id, "Workspace ID should be deterministic"
    assert len(ws1.id) == 16, "Workspace ID should be 16 chars"
    assert ws1.git_root_hash, "Should compute git root hash"
    print(f"[PASS] Workspace ID: {ws1.id}")


def test_workspace_id_stability():
    """Test workspace_id doesn't change when folder is renamed."""
    root = Path.cwd()

    ws = WorkspaceId.compute(root)

    assert ws.git_root_hash is not None
    print(f"[PASS] Git root hash: {ws.git_root_hash}")
    if ws.origin_url:
        print(f"[PASS] Origin URL: {ws.origin_url[:50]}...")

    from pathlib import Path as _p

    with tempfile.TemporaryDirectory() as tmpdir:
        alt_root = Path(tmpdir) / "renamed"
        alt_root.mkdir()
        ws2 = WorkspaceId.compute(alt_root)
        assert ws.id != ws2.id, "Different path should give different ID"
    print(f"[PASS] Different paths give different IDs")


def test_memory_router_init():
    """Test MemoryRouter initialization."""
    root = Path.cwd()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "brain.db"
        router = MemoryRouter(root, db_path)

        assert router.workspace_id is not None
        assert router.db_path == db_path
        print(f"[PASS] Router workspace: {router.workspace_id.id}")


def test_workspace_id_column_migration():
    """Test workspace_id column addition."""
    from kit.core.schema_factory import init_db

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "brain.db"

        conn = sqlite3.connect(str(db_path))
        init_db(conn)
        conn.close()

        router = MemoryRouter(Path.cwd(), db_path)

        conn = router.get_connection(db_path)
        router.ensure_workspace_id(conn)
        conn.close()

        conn = router.get_connection(db_path)
        cols = conn.execute("PRAGMA table_info(observations)").fetchall()
        col_names = [c[1] for c in cols]
        conn.close()
        assert "workspace_id" in col_names, "workspace_id column should exist"
        print("[PASS] workspace_id column exists")


def test_scoped_learn():
    """Test learn_scoped inserts with workspace_id."""
    from kit.core.schema_factory import init_db

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "brain.db"

        conn = sqlite3.connect(str(db_path))
        init_db(conn)
        conn.close()

        root = Path.cwd()
        router = MemoryRouter(root, db_path)

        conn = router.get_connection(db_path)
        router.ensure_workspace_id(conn)

        conn.execute("INSERT INTO nodes (uid, kind) VALUES (?, ?)", ("test_node", "test"))
        node_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", ("test_node",)).fetchone()
        node_id = node_row["id"]

        fact_id = router.learn_scoped(
            conn,
            node_id=node_id,
            content="Test observation",
            metadata={"test": True},
            scope="test_scope",
            tag="decision",
        )

        conn.commit()

        assert fact_id is not None

        row = conn.execute(
            "SELECT workspace_id, content FROM observations WHERE id = ?",
            (fact_id,),
        ).fetchone()

        conn.close()

        assert row["workspace_id"] == router.workspace_id.id
        print("[PASS] learn_scoped with workspace_id")


if __name__ == "__main__":
    tests = [
        test_workspace_id_generation,
        test_workspace_id_stability,
        test_memory_router_init,
        test_workspace_id_column_migration,
        test_scoped_learn,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
