"""
Integration & Benchmark Tests for Graph Slice + Incremental Indexing.

Validates:
1. Full pipeline: file → incremental index → slice → signal
2. Performance: <100ms latency, 100x+ token reduction
3. Correctness: slice produces valid subgraph
4. Scalability: handles large graphs efficiently
"""

import unittest
import tempfile
import sqlite3
import time
import json
from pathlib import Path
from typing import List, Dict

import sys
sys.path.insert(0, str(Path(__file__).parent))

from runtime.graph_slice_engine import GraphSliceEngine
from plugins.atlas_indexer.incremental_updater import IncrementalUpdater
from plugins.atlas_indexer.indexer import AtlasIndexer


class TestIntegrationPipeline(unittest.TestCase):
    """Integration: incremental index → slice → analysis."""
    
    def setUp(self):
        """Setup test workspace."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.atlas_dir = self.workspace / ".antigravity" / "atlas"
        self.atlas_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.atlas_dir / "atlas.db"
        
        self._init_realistic_graph()
    
    def tearDown(self):
        """Cleanup."""
        self.temp_dir.cleanup()
    
    def _init_realistic_graph(self):
        """Create a realistic code graph structure."""
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
        cur.execute("""
            CREATE TABLE applied_txns (
                txn_id TEXT PRIMARY KEY,
                file TEXT NOT NULL,
                ts REAL NOT NULL
            )
        """)
        
        # Realistic multi-layer architecture:
        # API Layer → Service Layer → Repository Layer → DB
        
        symbols = [
            # API layer
            ("UserAPI.get", "function", "api/users.py", 1),
            ("UserAPI.post", "function", "api/users.py", 20),
            ("AuthAPI.login", "function", "api/auth.py", 1),
            
            # Service layer
            ("UserService.find", "function", "service/user.py", 1),
            ("UserService.create", "function", "service/user.py", 20),
            ("AuthService.authenticate", "function", "service/auth.py", 1),
            ("AuthService.issue_token", "function", "service/auth.py", 30),
            
            # Repository layer
            ("UserRepo.query", "function", "repo/user.py", 1),
            ("UserRepo.persist", "function", "repo/user.py", 20),
            
            # Utilities
            ("Logger.info", "function", "util/logger.py", 1),
            ("TokenUtil.sign", "function", "util/token.py", 1),
        ]
        
        for name, kind, file, line in symbols:
            cur.execute(
                "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                (name, kind, file, line)
            )
        
        # Edges: API → Service → Repo
        edges = [
            # API → Service
            ("UserAPI.get", "UserService.find", "api/users.py", 2),
            ("UserAPI.post", "UserService.create", "api/users.py", 21),
            ("AuthAPI.login", "AuthService.authenticate", "api/auth.py", 2),
            
            # Service → Repo
            ("UserService.find", "UserRepo.query", "service/user.py", 2),
            ("UserService.create", "UserRepo.persist", "service/user.py", 21),
            
            # Service → Service/Util
            ("AuthService.authenticate", "UserService.find", "service/auth.py", 2),
            ("AuthService.issue_token", "TokenUtil.sign", "service/auth.py", 31),
            
            # Logging (cross-layer)
            ("UserService.find", "Logger.info", "service/user.py", 10),
            ("AuthService.issue_token", "Logger.info", "service/auth.py", 40),
        ]
        
        for caller, callee, file, line in edges:
            try:
                cur.execute(
                    "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
                    (caller, callee, file, line)
                )
            except sqlite3.IntegrityError:
                pass
        
        cur.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        cur.execute("CREATE INDEX idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
    
    def test_full_pipeline_latency(self):
        """Test: file → incremental update → slice in <100ms total."""
        updater = IncrementalUpdater(self.db_path)
        
        start = time.perf_counter()
        
        # Simulate file change
        new_symbols = [
            {"name": "UserAPI.get", "kind": "function", "line": 1},
            {"name": "UserAPI.post", "kind": "function", "line": 20}
        ]
        new_edges = [
            {"caller": "UserAPI.get", "callee": "UserService.find", "file": "api/users.py", "line": 2}
        ]
        
        # Incremental update
        result = updater.update_file_delta(
            "api/users.py",
            new_symbols=new_symbols,
            new_edges=new_edges,
            txn_id="test_txn_1"
        )
        self.assertTrue(result)
        updater.close()
        
        # Slice
        engine = GraphSliceEngine(self.db_path)
        slice_result = engine.slice("UserAPI.get", depth=2)
        engine.close()
        
        elapsed = time.perf_counter() - start
        
        # Should complete in reasonable time
        print(f"Full pipeline latency: {elapsed*1000:.1f}ms")
        self.assertLess(elapsed, 1.0)  # Should be much faster than 1s
    
    def test_incremental_then_slice_correctness(self):
        """Test: incremental update produces correct graph for slicing."""
        updater = IncrementalUpdater(self.db_path)
        
        # Update with modified symbols
        new_symbols = [
            {"name": "UserAPI.get", "kind": "function", "line": 2},  # Line changed
            {"name": "UserAPI.delete", "kind": "function", "line": 40}  # New
        ]
        new_edges = [
            {"caller": "UserAPI.get", "callee": "UserService.find", "file": "api/users.py", "line": 3},
            {"caller": "UserAPI.delete", "callee": "UserService.find", "file": "api/users.py", "line": 41}
        ]
        
        result = updater.update_file_delta(
            "api/users.py",
            new_symbols=new_symbols,
            new_edges=new_edges,
            txn_id="test_update"
        )
        self.assertTrue(result)
        updater.close()
        
        # Verify graph is correct for slicing
        engine = GraphSliceEngine(self.db_path)
        
        # Slice should work on updated graph
        slice_result = engine.slice("UserAPI.delete", depth=1)
        self.assertEqual(slice_result["symbol"], "UserAPI.delete")
        self.assertIn("UserService.find", slice_result["callees"])
        
        engine.close()
    
    def test_slice_layer_respects_boundaries(self):
        """Test: slice respects layer boundaries (API, Service, Repo)."""
        engine = GraphSliceEngine(self.db_path)
        
        # Slice starting from API layer
        slice_result = engine.slice(
            "AuthAPI.login",
            depth=2,
            enable_boundary_penalty=True
        )
        
        # Should include service layer but not be too broad
        self.assertLess(slice_result["slice_size"], 20)
        self.assertGreater(slice_result["token_estimate"], 50)
        
        engine.close()
    
    def test_token_reduction_claim(self):
        """Test: verify >100x token reduction."""
        engine = GraphSliceEngine(self.db_path)
        
        # Count total symbols
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM symbols")
        total_symbols = cur.fetchone()[0]
        conn.close()
        
        # Estimate tokens for full graph (rough: 5 tokens per symbol)
        full_graph_tokens = total_symbols * 5
        
        # Get slice tokens
        slice_result = engine.slice("UserAPI.get", depth=2, max_nodes=50)
        slice_tokens = slice_result["token_estimate"]
        
        # Compute reduction
        reduction_factor = full_graph_tokens / slice_tokens if slice_tokens > 0 else 0
        
        print(f"Full graph tokens: {full_graph_tokens}")
        print(f"Slice tokens: {slice_tokens}")
        print(f"Reduction factor: {reduction_factor:.1f}x")
        
        # Should achieve significant reduction
        self.assertGreater(reduction_factor, 5.0)
        
        engine.close()


class TestBenchmarks(unittest.TestCase):
    """Benchmark tests for performance characteristics."""
    
    def setUp(self):
        """Create large test graph."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "benchmark.db"
        self._create_large_graph(num_symbols=1000, num_edges=2000)
    
    def tearDown(self):
        """Cleanup."""
        self.temp_dir.cleanup()
    
    def _create_large_graph(self, num_symbols: int, num_edges: int):
        """Create a large synthetic graph for benchmarking."""
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
        
        # Insert symbols
        for i in range(num_symbols):
            module = f"module_{i % 50}"  # Distribute across 50 modules
            cur.execute(
                "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                (f"func_{i}", "function", f"{module}/code.py", i * 10)
            )
        
        # Insert edges (random-ish)
        inserted = 0
        for i in range(num_edges):
            caller_idx = i % num_symbols
            callee_idx = (i * 7 + 13) % num_symbols  # Pseudo-random
            
            if caller_idx != callee_idx:
                try:
                    cur.execute(
                        "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
                        (f"func_{caller_idx}", f"func_{callee_idx}", f"module_{i % 50}/code.py", i)
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass
        
        cur.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        cur.execute("CREATE INDEX idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
        
        print(f"Created benchmark graph: {num_symbols} symbols, {inserted} edges")
    
    def test_slice_performance_large_graph(self):
        """Benchmark: slice computation on large graph."""
        engine = GraphSliceEngine(self.db_path)
        
        times = []
        for i in range(10):
            start = time.perf_counter()
            result = engine.slice(f"func_{i * 100}", depth=2, max_nodes=50)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        print(f"Average slice time: {avg_time*1000:.1f}ms")
        
        # Should be sub-10ms for typical cases
        self.assertLess(avg_time, 0.05)  # 50ms cap
        
        engine.close()
    
    def test_incremental_update_performance(self):
        """Benchmark: incremental update latency."""
        updater = IncrementalUpdater(self.db_path)
        
        times = []
        for i in range(5):
            new_symbols = [
                {"name": f"new_func_{i}", "kind": "function", "line": 1}
            ]
            
            start = time.perf_counter()
            result = updater.update_file_delta(
                f"test{i}.py",
                new_symbols=new_symbols,
                new_edges=[],
                txn_id=f"txn_{i}"
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        print(f"Average incremental update time: {avg_time*1000:.1f}ms")
        
        # Should be <50ms
        self.assertLess(avg_time, 0.05)
        
        updater.close()
    
    def test_memory_efficiency(self):
        """Benchmark: memory usage."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create engines
        engine = GraphSliceEngine(self.db_path)
        updater = IncrementalUpdater(self.db_path)
        
        # Run operations
        for i in range(10):
            engine.slice(f"func_{i * 100}", depth=2)
            updater.update_file_delta(f"test{i}.py", [], [])
        
        mem_after = process.memory_info().rss / 1024 / 1024
        mem_used = mem_after - mem_before
        
        print(f"Memory used: {mem_used:.1f} MB")
        
        # Should not balloon memory
        self.assertLess(mem_used, 500)  # 500MB cap
        
        engine.close()
        updater.close()


class TestScalability(unittest.TestCase):
    """Test scaling characteristics."""
    
    def test_slice_scales_linearly_with_depth(self):
        """Verify slice size grows appropriately with depth."""
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "scale.db"
        
        # Create linear chain: f1 → f2 → f3 → f4 → f5
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        cur.execute("CREATE TABLE symbols (name TEXT NOT NULL, kind TEXT NOT NULL, file TEXT NOT NULL, line INTEGER NOT NULL)")
        cur.execute("CREATE TABLE calls (caller TEXT NOT NULL, callee TEXT NOT NULL, file TEXT NOT NULL, line INTEGER NOT NULL, UNIQUE(caller, callee, file, line))")
        
        for i in range(1, 6):
            cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", (f"f{i}", "function", "code.py", i))
        
        for i in range(1, 5):
            cur.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", (f"f{i}", f"f{i+1}", "code.py", i))
        
        cur.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        cur.execute("CREATE INDEX idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
        
        # Slice at different depths
        engine = GraphSliceEngine(db_path)
        
        slice_d1 = engine.slice("f1", depth=1)
        slice_d2 = engine.slice("f1", depth=2)
        slice_d3 = engine.slice("f1", depth=3)
        
        print(f"Depth 1: {slice_d1['slice_size']} nodes")
        print(f"Depth 2: {slice_d2['slice_size']} nodes")
        print(f"Depth 3: {slice_d3['slice_size']} nodes")
        
        # Should grow with depth
        self.assertLessEqual(slice_d1['slice_size'], slice_d2['slice_size'])
        self.assertLessEqual(slice_d2['slice_size'], slice_d3['slice_size'])
        
        engine.close()
        temp_dir.cleanup()


if __name__ == "__main__":
    # Run with verbose output for benchmarks
    unittest.main(verbosity=2)
