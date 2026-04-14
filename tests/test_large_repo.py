import time
import pytest
from pathlib import Path
from kit.core.file_system import safe_walk

def test_large_repo_performance(tmp_path):
    """
    Verify that safe_walk can handle 1000 files efficiently.
    """
    total_files = 1000
    files_per_dir = 50
    num_dirs = total_files // files_per_dir
    
    # Create mock repo
    for d in range(num_dirs):
        dir_path = tmp_path / f"dir_{d}"
        dir_path.mkdir()
        for f in range(files_per_dir):
            file_path = dir_path / f"file_{f}.py"
            file_path.write_text("pass")
            
    # Add some garbage dirs that should be ignored
    (tmp_path / "node_modules").mkdir()
    for i in range(100):
        (tmp_path / "node_modules" / f"junk_{i}.js").write_text("junk")
        
    start_time = time.time()
    results = list(safe_walk(tmp_path))
    end_time = time.time()
    
    elapsed = end_time - start_time
    
    # Verify file count
    assert len(results) == total_files
    
    # Performance check: 1000 files should be scanned in < 1 second locally
    # The user suggested < 5 seconds for "realism", we aim higher.
    print(f"\nScanned {len(results)} files in {elapsed:.4f}s")
    assert elapsed < 5.0
