from pathlib import Path

import pytest

from kit.core.kit_cognitive_core import SAMBrain


@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "restore_test.db"
    return SAMBrain(db_path, root_path=tmp_path)


def test_snapshot_restore_cycle(brain, tmp_path):
    """
    Titanium Recovery Test (Priority 2).
    Verify that restoring from a snapshot actually works.
    """
    # 1. State A: Initial data
    brain.learn("initial", "This is the initial state.", tag="note")
    snapshot_path = brain.snapshot()
    assert snapshot_path.exists()

    # v1.2.5: Save to a separate file so the auto-syncer doesn't overwrite it
    import shutil

    safe_snapshot = tmp_path / "safe_baseline.db"
    shutil.copy2(snapshot_path, safe_snapshot)

    # 2. State B: More data
    brain.learn("volatile", "This should be gone after restore.", tag="note")
    results = brain.search("gone")
    assert len(results) == 1

    # 3. Restore to State A
    success = brain.restore(safe_snapshot)
    assert success

    # 4. Verify results
    # Search for initial should still work
    results_initial = brain.search("initial")
    assert len(results_initial) == 1

    # Search for volatile should fail
    results_volatile = brain.search("gone")
    assert len(results_volatile) == 0

    print("\n[RECOVERY] Snapshot/Restore cycle verified successfully.")
