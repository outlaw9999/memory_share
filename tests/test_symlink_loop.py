import pytest
import os
from pathlib import Path
from kit.core.file_system import safe_walk

def test_symlink_recursion_protection(tmp_path):
    """
    Test that safe_walk correctly handles circular symlinks.
    """
    # Create structure: a/b -> a
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    
    link_b = dir_a / "b"
    # Windows requires admin or specific settings to create symlinks, 
    # but junctions work similarly for directory loops.
    # On non-Windows,os.symlink works.
    try:
        os.symlink(dir_a, link_b, target_is_directory=True)
    except OSError:
        pytest.skip("Could not create symlink (likely permission issue on Windows)")

    # We should only visit dir_a once (or twice if follow_symlinks=True, but inode tracking should prevent loop)
    # Our safe_walk by default doesn't follow symlinks to dirs.
    results = list(safe_walk(dir_a, follow_symlinks=True))
    
    # Even with follow_symlinks=True, the inode check should stop it.
    # 'a' visited. Then 'a/b' is 'a'. Inode matches. Return.
    assert len(results) == 0 # No files in this test, just directories.
    # The important part is that it DOES NOT CRASH.

def test_hardlink_recursion_protection(tmp_path):
    """
    Test that safe_walk handles hardlink loops if they were possible 
    (not possible for dirs, but we test inode tracking logic on files).
    """
    file_a = tmp_path / "a.py"
    file_a.write_text("print('hello')")
    
    file_b = tmp_path / "b.py"
    try:
        os.link(file_a, file_b) # Hardlink
    except OSError:
        pytest.skip("Could not create hardlink")

    results = list(safe_walk(tmp_path))
    # Inode tracking should see file_a and file_b as the same.
    # Depending on order, we might get one or the other.
    assert len(results) == 1
    assert results[0].name in ("a.py", "b.py")

def test_depth_limit(tmp_path):
    """
    Verify max_depth limit.
    """
    curr = tmp_path
    for i in range(10):
        curr = curr / f"depth_{i}"
        curr.mkdir()
    
    # Add a file at depth 10
    target_file = curr / "deep.py"
    target_file.write_text("pass")
    
    # Walk with depth limit 5
    results = list(safe_walk(tmp_path, max_depth=5))
    assert len(results) == 0
    
    # Walk with depth limit 15
    results = list(safe_walk(tmp_path, max_depth=15))
    assert len(results) == 1
    assert results[0].name == "deep.py"
