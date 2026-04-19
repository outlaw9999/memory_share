import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_kit(*args, cwd=None):
    """v1.2.4-LOCK: Uses canonical entrypoint `python -m kit`."""
    cmd = [sys.executable, "-m", "kit"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)


def test_kit_scan_basic(tmp_path):
    """
    Verify that kit scan finds allowed files and ignores excluded ones.
    """
    # Create mock structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.js").write_text("console.log('test')")

    # Files that should be IGNORED
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("junk")
    (tmp_path / "data.json").write_text("{}")
    (tmp_path / "README.md").write_text("# Readme")

    res = run_kit("scan", cwd=tmp_path)

    # If the command isn't implemented yet, it will fail with invalid choice
    if "invalid choice: 'scan'" in res.stderr:
        pytest.fail("kit scan command not implemented yet")

    # Nếu lệnh fail, in ra stderr để debug
    if res.returncode != 0:
        print(res.stderr)
    assert res.returncode == 0
    stdout = res.stdout

    # Check for expected files (use normalized paths or check basename)
    assert "main.py" in stdout
    assert "utils.js" in stdout

    # Check for ignored files (should NOT be there)
    assert "node_modules" not in stdout
    assert "data.json" not in stdout
    assert "README.md" not in stdout


def test_kit_scan_empty(tmp_path):
    """
    Handle empty directories gracefully.
    """
    res = run_kit("scan", cwd=tmp_path)
    assert res.returncode == 0
    assert "Total discovered files: 0" in res.stdout
