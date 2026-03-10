"""
Unit tests for Graph Slice Engine and Incremental Graph Indexing.

Tests verify:
1. Graph Slice algorithm correctness (BFS, ranking)
2. Incremental updater delta computation
3. Symbol hash stability
4. Token estimation accuracy
"""

import unittest
import tempfile
import sqlite3
import json
from pathlib import Path
from typing import List, Dict

# Add runtime to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.graph_slice_engine import GraphSliceEngine
from plugins.atlas_indexer.incremental_updater import IncrementalUpdater, SymbolHasher
from plugins.atlas_indexer.graph_store import GraphStore


class TestSymbolHasher(unittest.TestCase):
    """Test symbol hash stability."""
    
    def test_same_content_same_hash(self):
        """Same symbol content produces same hash."""
        hash1 = SymbolHasher.compute(
            name="login",
            kind="function",
            signature="(self, user: str) -> Token",
            body="def login(self, user):\n    return self.token_service.issue(user)"
        )
        hash2 = SymbolHasher.compute(
            name="login",
            kind="function",
            signature="(self, user: str) -> Token",
            body="def login(self, user):\n    return self.token_service.issue(user)"
        )
        self.assertEqual(hash1, hash2)
    
    def test_different_body_different_hash(self):
        """Different function body produces different hash."""
        hash1 = SymbolHasher.compute(
            name="login",
            kind="function",
            body="def login(self):\n    return True"
        )
        hash2 = SymbolHasher.compute(
            name="login",
            kind="function",
            body="def login(self):\n    return False"
        )
        self.assertNotEqual(hash1, hash2)
    
    def test_different_signature_different_hash(self):
        """Different signature produces different hash."""
        hash1 = SymbolHasher.compute(
            name="process",
            kind="function",
            signature="(data: str)"
        )
        hash2 = SymbolHasher.compute(
            name="process",
            kind="function",
            signature="(data: str, options: dict)"
        )
        self.assertNotEqual(hash1, hash2)


class TestIncrementalUpdater(unittest.TestCase):
    """Test incremental graph update logic."""
    
    def setUp(self):
        """Create temporary test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self._init_test_db()
        self.updater = IncrementalUpdater(self.db_path)
    
    def tearDown(self):
        """Cleanup."""
        self.updater.close()
        self.temp_dir.cleanup()
    
    def _init_test_db(self):
        """Initialize test database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create schema
        cur.execute("""
            CREATE TABLE symbols (
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE calls (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                UNIQUE(caller, callee, file, line)
            )
        """)
        cur.execute("""
            CREATE TABLE applied_txns (
                txn_id TEXT PRIMARY KEY,
                file TEXT NOT NULL,
                ts REAL NOT NULL
            )
        """)
        cur.execute("CREATE INDEX idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        cur.execute("CREATE INDEX idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
    
    def test_add_symbols(self):
        """Test adding new symbols to empty file."""
        new_symbols = [
            {"name": "main", "kind": "function", "line": 1},
            {"name": "helper", "kind": "function", "line": 10}
        ]
        new_edges = []
        
        result = self.updater.update_file_delta(
            "main.py",
            new_symbols=new_symbols,
            new_edges=new_edges
        )
        
        self.assertTrue(result)
        
        # Verify symbols were inserted
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM symbols WHERE file = ?", ("main.py",))
        count = cur.fetchone()[0]
        self.assertEqual(count, 2)
        conn.close()
    
    def test_remove_symbols(self):
        """Test removing symbols."""
        # First insert
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
            ("old_func", "function", "test.py", 1)
        )
        conn.commit()
        
        # Then update with different symbols (simulating removal)
        self.updater = IncrementalUpdater(self.db_path)
        new_symbols = [
            {"name": "new_func", "kind": "function", "line": 1}
        ]
        
        result = self.updater.update_file_delta(
            "test.py",
            new_symbols=new_symbols,
            new_edges=[]
        )
        
        self.assertTrue(result)
        
        # Verify old symbol was deleted
        cur.execute("SELECT COUNT(*) FROM symbols WHERE name = ?", ("old_func",))
        count = cur.fetchone()[0]
        self.assertEqual(count, 0)
        
        conn.close()
    
    def test_duplicate_update_returns_false(self):
        """Test that duplicate updates return False."""
        new_symbols = [
            {"name": "func", "kind": "function", "line": 1}
        ]
        new_edges = []
        
        # First update succeeds
        result1 = self.updater.update_file_delta(
            "test.py",
            new_symbols=new_symbols,
            new_edges=new_edges,
            txn_id="txn1"
        )
        self.assertTrue(result1)
        
        # Second identical update should fail (duplicate)
        result2 = self.updater.update_file_delta(
            "test.py",
            new_symbols=new_symbols,
            new_edges=new_edges,
            txn_id="txn2"
        )
        self.assertFalse(result2)
    
    def test_add_edges(self):
        """Test adding call edges."""
        # Insert symbols first
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                   ("caller", "function", "test.py", 1))
        cur.execute("INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                   ("callee", "function", "test.py", 10))
        conn.commit()
        conn.close()
        
        # Re-init updater
        self.updater = IncrementalUpdater(self.db_path)
        
        # Now add edge
        new_symbols = [
            {"name": "caller", "kind": "function", "line": 1},
            {"name": "callee", "kind": "function", "line": 10}
        ]
        new_edges = [
            {"caller": "caller", "callee": "callee", "file": "test.py", "line": 2}
        ]
        
        result = self.updater.update_file_delta(
            "test.py",
            new_symbols=new_symbols,
            new_edges=new_edges
        )
        
        self.assertTrue(result)
        
        # Verify edge was inserted
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM calls WHERE caller = ? AND callee = ?",
                   ("caller", "callee"))
        count = cur.fetchone()[0]
        self.assertEqual(count, 1)
        conn.close()


class TestGraphSliceEngine(unittest.TestCase):
    """Test graph slicing algorithm."""
    
    def setUp(self):
        """Create test database with sample graph."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "slice_test.db"
        self._init_test_graph()
        self.engine = GraphSliceEngine(self.db_path)
    
    def tearDown(self):
        """Cleanup."""
        self.engine.close()
        self.temp_dir.cleanup()
    
    def _init_test_graph(self):
        """Create sample graph for testing."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Schema
        cur.execute("""
            CREATE TABLE symbols (
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE calls (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                UNIQUE(caller, callee, file, line)
            )
        """)
        
        # Sample symbols
        symbols = [
            ("main", "function", "app.py", 1),
            ("login", "function", "auth/service.py", 10),
            ("issue_token", "function", "auth/service.py", 20),
            ("find_user", "function", "auth/repo.py", 30),
            ("log_event", "function", "logging/service.py", 40)
        ]
        
        for name, kind, file, line in symbols:
            cur.execute(
                "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                (name, kind, file, line)
            )
        
        # Sample edges
        edges = [
            ("main", "login", "app.py", 2),
            ("login", "issue_token", "auth/service.py", 11),
            ("login", "find_user", "auth/service.py", 12),
            ("login", "log_event", "logging/service.py", 13),
            ("issue_token", "log_event", "auth/service.py", 21)
        ]
        
        for caller, callee, file, line in edges:
            try:
                cur.execute(
                    "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
                    (caller, callee, file, line)
                )
            except sqlite3.IntegrityError:
                pass
        
        # Indexes
        cur.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        cur.execute("CREATE INDEX idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
    
    def test_find_symbol(self):
        """Test finding symbol in database."""
        sym = self.engine._find_symbol("login")
        self.assertIsNotNone(sym)
        self.assertEqual(sym["name"], "login")
        self.assertEqual(sym["file"], "auth/service.py")
    
    def test_get_neighbors(self):
        """Test finding neighbors of a symbol."""
        neighbors = self.engine._get_neighbors("login")
        
        # login is called by main, calls issue_token and find_user
        self.assertIn("main", neighbors)
        self.assertIn("issue_token", neighbors)
        self.assertIn("find_user", neighbors)
    
    def test_compute_centrality(self):
        """Test centrality computation."""
        # login has high centrality (called by main, calls 2 others)
        centrality_login = self.engine._compute_centrality("login")
        self.assertGreater(centrality_login, 0)
        
        # log_event has moderate centrality
        centrality_log = self.engine._compute_centrality("log_event")
        self.assertGreaterEqual(centrality_log, 0)
    
    def test_slice_basic(self):
        """Test basic slice extraction."""
        result = self.engine.slice("login", depth=2, max_nodes=10)
        
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "login")
        self.assertIn("slice_size", result)
        self.assertIn("callers", result)
        self.assertIn("callees", result)
        self.assertIn("nodes", result)
        
        # Should include at least login, callers, and callees
        self.assertGreaterEqual(result["slice_size"], 1)
        self.assertIn("login", result["nodes"])
    
    def test_slice_depth_limiting(self):
        """Test that depth parameter limits BFS."""
        slice_depth1 = self.engine.slice("main", depth=1, max_nodes=100)
        slice_depth2 = self.engine.slice("main", depth=2, max_nodes=100)
        
        # Depth 2 should find more nodes than depth 1
        self.assertGreaterEqual(slice_depth2["slice_size"], slice_depth1["slice_size"])
    
    def test_slice_max_nodes_respected(self):
        """Test that max_nodes limit is respected."""
        result = self.engine.slice("main", depth=3, max_nodes=3)
        
        # Should not exceed max_nodes
        self.assertLessEqual(result["slice_size"], 3)
    
    def test_slice_token_estimate(self):
        """Test token estimation is reasonable."""
        result = self.engine.slice("login", depth=2, max_nodes=50)
        
        # Token estimate should be positive and reasonable
        self.assertGreater(result["token_estimate"], 0)
        self.assertLess(result["token_estimate"], 10000)  # Sanity check
    
    def test_slice_nonexistent_symbol(self):
        """Test slicing nonexistent symbol."""
        result = self.engine.slice("nonexistent_symbol", depth=2)
        
        self.assertIn("error", result)


class TestIntegration(unittest.TestCase):
    """Integration tests combining slice + incremental."""
    
    def setUp(self):
        """Create integrated test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "integrated.db"
        self._init_integrated_db()
    
    def tearDown(self):
        """Cleanup."""
        self.temp_dir.cleanup()
    
    def _init_integrated_db(self):
        """Create test database with full schema."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE symbols (
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE calls (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                UNIQUE(caller, callee, file, line)
            )
        """)
        cur.execute("""
            CREATE TABLE applied_txns (
                txn_id TEXT PRIMARY KEY,
                file TEXT NOT NULL,
                ts REAL NOT NULL
            )
        """)
        
        cur.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        cur.execute("CREATE INDEX idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
    
    def test_incremental_then_slice(self):
        """Test: add symbols with incremental, then slice."""
        updater = IncrementalUpdater(self.db_path)
        
        # Phase 1: Incremental add
        symbols = [
            {"name": "api", "kind": "function", "line": 1},
            {"name": "service", "kind": "function", "line": 10},
            {"name": "repo", "kind": "function", "line": 20}
        ]
        edges = [
            {"caller": "api", "callee": "service", "file": "api.py", "line": 2},
            {"caller": "service", "callee": "repo", "file": "service.py", "line": 11}
        ]
        
        result = updater.update_file_delta("api.py", symbols=symbols, edges=edges)
        self.assertTrue(result)
        
        updater.close()
        
        # Phase 2: Slice
        engine = GraphSliceEngine(self.db_path)
        slice_result = engine.slice("api", depth=2, max_nodes=10)
        
        self.assertEqual(slice_result["symbol"], "api")
        self.assertGreater(slice_result["slice_size"], 0)
        
        engine.close()


if __name__ == "__main__":
    unittest.main()
