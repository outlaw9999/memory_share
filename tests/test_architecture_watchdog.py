"""
Tests for Architecture Watchdog - Autonomous Drift Detection.

Tests verify:
1. Circular dependency detection
2. Layer violation detection
3. God module detection
4. Cyclomatic complexity spike detection
5. CI/CD integration patterns
"""

import unittest
import tempfile
import sqlite3
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from kit.architecture_watchdog import (
    ArchitectureWatchdog,
    ArchitecturePolicy,
    ViolationType
)


class TestArchitectureWatchdog(unittest.TestCase):
    """Test architecture violation detection."""
    
    def setUp(self):
        """Create test database with architecture issues."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "watchdog_test.db"
        self._init_test_db()
        
        # Default policy
        self.policy = ArchitecturePolicy(
            layers=["api", "service", "repo", "util"],
            max_fanout=10,
            max_god_module_size=100
        )
        
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
    
    def tearDown(self):
        """Cleanup."""
        self.watchdog.close()
        self.temp_dir.cleanup()
    
    def _init_test_db(self):
        """Initialize test database."""
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
        
        cur.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX idx_calls_caller ON calls(caller)")
        
        conn.commit()
        conn.close()
    
    def test_circular_dependency_detection(self):
        """Test detection of A → B → A cycles."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create symbols
        symbols = [
            ("AuthService", "class", "api/auth.py", 1),
            ("TokenService", "class", "service/token.py", 1),
            ("CacheManager", "class", "util/cache.py", 1)
        ]
        
        for name, kind, file, line in symbols:
            cur.execute(
                "INSERT INTO symbols VALUES (?, ?, ?, ?)",
                (name, kind, file, line)
            )
        
        # Create circular dependency: Auth → Token → Auth
        edges = [
            ("AuthService", "TokenService", "api/auth.py", 2),
            ("TokenService", "AuthService", "service/token.py", 2)
        ]
        
        for caller, callee, file, line in edges:
            cur.execute(
                "INSERT INTO calls VALUES (?, ?, ?, ?)",
                (caller, callee, file, line)
            )
        
        conn.commit()
        conn.close()
        
        # Re-init watchdog to read new data
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        
        # Scan
        violations = self.watchdog.scan_changes(["api/auth.py"])
        
        # Should detect cycle
        cycles = [v for v in violations if v.violation_type == ViolationType.CIRCULAR_DEPENDENCY]
        self.assertGreater(len(cycles), 0)
    
    def test_layer_violation_detection(self):
        """Test detection of invalid layer crossing (util → api)."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create symbols in different layers
        symbols = [
            ("LogUtil", "function", "util/logger.py", 1),
            ("AuthAPI", "endpoint", "api/auth.py", 1)
        ]
        
        for name, kind, file, line in symbols:
            cur.execute(
                "INSERT INTO symbols VALUES (?, ?, ?, ?)",
                (name, kind, file, line)
            )
        
        # util should NOT call api (wrong direction)
        cur.execute(
            "INSERT INTO calls VALUES (?, ?, ?, ?)",
            ("LogUtil", "AuthAPI", "util/logger.py", 2)
        )
        
        conn.commit()
        conn.close()
        
        # Re-init watchdog
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        
        # Scan
        violations = self.watchdog.scan_changes(["util/logger.py"])
        
        # Should detect layer violation
        layer_viols = [v for v in violations if v.violation_type == ViolationType.LAYER_VIOLATION]
        self.assertGreater(len(layer_viols), 0)
    
    def test_god_module_detection(self):
        """Test detection of files with too many symbols."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create many symbols in one file (exceeding max_god_module_size)
        for i in range(self.policy.max_god_module_size + 10):
            cur.execute(
                "INSERT INTO symbols VALUES (?, ?, ?, ?)",
                (f"func_{i}", "function", "service/monolith.py", i)
            )
        
        conn.commit()
        conn.close()
        
        # Re-init watchdog
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        
        # Scan
        violations = self.watchdog.scan_changes(["service/monolith.py"])
        
        # Should detect god module
        god_modules = [v for v in violations if v.violation_type == ViolationType.GOD_MODULE]
        self.assertGreater(len(god_modules), 0)
    
    def test_cyclomatic_spike_detection(self):
        """Test detection of high fanout (many callees)."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create symbol
        cur.execute(
            "INSERT INTO symbols VALUES (?, ?, ?, ?)",
            ("Router", "class", "api/router.py", 1)
        )
        
        # Create many callees for Router (exceeding max_fanout)
        for i in range(self.policy.max_fanout + 5):
            target = f"handler_{i}"
            cur.execute(
                "INSERT INTO symbols VALUES (?, ?, ?, ?)",
                (target, "function", f"api/handlers/{i}.py", 1)
            )
            cur.execute(
                "INSERT INTO calls VALUES (?, ?, ?, ?)",
                ("Router", target, "api/router.py", i+2)
            )
        
        conn.commit()
        conn.close()
        
        # Re-init watchdog
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        
        # Scan
        violations = self.watchdog.scan_changes(["api/router.py"])
        
        # Should detect complexity spike
        spikes = [v for v in violations if v.violation_type == ViolationType.CYCLOMATIC_SPIKE]
        self.assertGreater(len(spikes), 0)
    
    def test_format_report(self):
        """Test human-readable report generation."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create circular dependency
        cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", ("A", "f", "a.py", 1))
        cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", ("B", "f", "b.py", 1))
        cur.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", ("A", "B", "a.py", 2))
        cur.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", ("B", "A", "b.py", 2))
        
        conn.commit()
        conn.close()
        
        # Re-init and scan
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        self.watchdog.scan_changes(["a.py"])
        
        # Format report
        report = self.watchdog.format_report()
        
        self.assertIn("Architecture Violations", report)
        self.assertIn("Circular dependency", report)
    
    def test_should_block_merge(self):
        """Test merge blocking decision."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Create error-level violation
        cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", ("A", "f", "util/a.py", 1))
        cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", ("B", "f", "api/b.py", 1))
        cur.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", ("A", "B", "util/a.py", 2))
        
        conn.commit()
        conn.close()
        
        # Re-init and scan
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        violations = self.watchdog.scan_changes(["util/a.py"])
        
        # Should block (layer violation is error-level)
        self.assertTrue(self.watchdog.should_block_merge())
    
    def test_json_export(self):
        """Test JSON export for CI/CD tools."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", ("A", "f", "a.py", 1))
        cur.execute("INSERT INTO symbols VALUES (?, ?, ?, ?)", ("B", "f", "b.py", 1))
        cur.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", ("A", "B", "a.py", 2))
        cur.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", ("B", "A", "b.py", 2))
        
        conn.commit()
        conn.close()
        
        self.watchdog = ArchitectureWatchdog(self.db_path, self.policy)
        self.watchdog.scan_changes(["a.py"])
        
        json_out = self.watchdog.to_json()
        
        # Should be valid JSON
        import json
        data = json.loads(json_out)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)


class TestCIDDIntegration(unittest.TestCase):
    """Test CI/CD integration patterns."""
    
    def test_github_actions_template(self):
        """Verify GitHub Actions workflow template is valid."""
        from kit.architecture_watchdog import GITHUB_ACTIONS_TEMPLATE
        
        # Should contain key elements
        self.assertIn("on: [pull_request]", GITHUB_ACTIONS_TEMPLATE)
        self.assertIn("Architecture Watchdog", GITHUB_ACTIONS_TEMPLATE)
        self.assertIn("git diff --name-only", GITHUB_ACTIONS_TEMPLATE)
    
    def test_pre_commit_template(self):
        """Verify pre-commit hook template is valid."""
        from kit.architecture_watchdog import PRE_COMMIT_TEMPLATE
        
        self.assertIn("#!/usr/bin/env python3", PRE_COMMIT_TEMPLATE)
        self.assertIn("git diff --name-only --cached", PRE_COMMIT_TEMPLATE)
        self.assertIn("should_block_merge()", PRE_COMMIT_TEMPLATE)


class TestPolicyCustomization(unittest.TestCase):
    """Test custom policy configuration."""
    
    def test_custom_layer_order(self):
        """Test custom layer hierarchy."""
        policy = ArchitecturePolicy(
            layers=["presentation", "business", "data"],
            allowed_transitions={
                "presentation": ["business", "data"],
                "business": ["data"],
                "data": []
            }
        )
        
        self.assertEqual(policy.layers[0], "presentation")
        self.assertTrue("business" in policy.allowed_transitions["presentation"])
    
    def test_custom_limits(self):
        """Test custom complexity limits."""
        policy = ArchitecturePolicy(
            max_fanout=5,
            max_god_module_size=50
        )
        
        self.assertEqual(policy.max_fanout, 5)
        self.assertEqual(policy.max_god_module_size, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
