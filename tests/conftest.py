import os
from pathlib import Path

import pytest


@pytest.fixture
def brain(tmp_path):
    from kit.core.memory_topology import MemoryTopologyFactory
    from kit.core.kit_cognitive_core import SAMBrain
    # v1.2.4-TITANIUM: Force topology-driven connection for test isolation
    # This ensures standardized URI pathing and schema initialization on Windows
    topology = MemoryTopologyFactory.for_project(tmp_path)
    db_path = topology.resolve("local", "local")
    return SAMBrain(db_path, root_path=tmp_path, topology=topology)


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Sets up the global environment for the entire test session."""
    test_root = Path.cwd() / ".kit_test_session"
    test_root.mkdir(exist_ok=True)
    
    # Override global home to avoid polluting user space
    # The 'SAMBrain' check uses 'pytest' in sys.modules, 
    # but we still set this for path consistency.
    os.environ["KIT_GLOBAL_HOME"] = str(test_root / "global")
    
    yield
