"""
Test Isolation Layer v1.2.4

Eliminates IDE lag by:
1. Direct API calls (no subprocess)
2. In-memory DB (no filesystem churn)
3. Disabled side-effect IO during tests
4. Mock environment variables

Usage:
    pytest tests/           # runs isolated
    pytest --no-isolation   # runs with full IO (for debugging only)
"""

import os
import sys
import tempfile
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

import pytest


# =========================
# Test Isolation Config
# =========================

TEST_ISOLATION_ENABLED = True
IN_MEMORY_SQLITE = True


@contextmanager
def test_isolation() -> Generator[None, None, None]:
    """
    Context manager for test isolation.
    
    When active:
    - Uses in-memory SQLite
    - Mocks environment for test-only paths
    - Disables file system watchers
    - No subprocess spawning
    """
    if not TEST_ISOLATION_ENABLED:
        yield
        return
    
    # Store original env
    original_env = dict(os.environ)
    
    # Create temp test home
    test_home = tempfile.mkdtemp(prefix="kit_test_")
    
    try:
        # Set test isolation environment
        os.environ["KIT_TEST_MODE"] = "1"
        os.environ["KIT_GLOBAL_HOME"] = test_home
        os.environ["KIT_DB_IN_MEMORY"] = "1" if IN_MEMORY_SQLITE else "0"
        
        # Disable noisy logging
        os.environ["KIT_LOG_LEVEL"] = "ERROR"
        
        yield
        
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


def pytest_configure(config):
    """Pytest hook for test isolation."""
    if config.getoption("--no-isolation", default=False):
        global TEST_ISOLATION_ENABLED
        TEST_ISOLATION_ENABLED = False
        print("\n⚠️  Test isolation DISABLED (--no-isolation)")


def pytest_addoption(parser):
    """Add isolation options."""
    parser.addoption(
        "--no-isolation",
        action="store_true",
        default=False,
        help="Disable test isolation (for debugging only)"
    )


@pytest.fixture
def brain(tmp_path):
    """
    Isolated brain fixture for tests.
    
    Uses in-memory SQLite when available.
    No subprocess, no filesystem pollution.
    
    Implements Shutdown Spec v1.0:
    1. Explicit cleanup
    2. Connection close
    3. GC collect
    4. Windows-safe delay
    """
    with test_isolation():
        from kit.core.memory_topology import MemoryTopologyFactory
        from kit.core.kit_cognitive_core import SAMBrain
        
        # Use isolated topology
        topology = MemoryTopologyFactory.for_project(tmp_path)
        db_path = topology.resolve("local", "local")
        
        # Return brain with test isolation
        brain = SAMBrain(db_path, root_path=tmp_path, topology=topology)
        yield brain
        
        # Shutdown Spec v1.0 - MUST run after each test
        try:
            brain.shutdown()
        except Exception:
            pass
        
        import gc
        gc.collect()
        
        # Windows-safe delay (release file handles)
        import time
        time.sleep(0.2)


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Sets up the global environment for the entire test session."""
    test_root = Path.cwd() / ".kit_test_session"
    test_root.mkdir(exist_ok=True)
    
    # Override global home to avoid polluting user space
    os.environ["KIT_GLOBAL_HOME"] = str(test_root / "global")
    
    yield