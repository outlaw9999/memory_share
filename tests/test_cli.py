import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_kit(*args, cwd=None):
    """Helper to run the kit CLI."""
    cmd = ["python", str(REPO_ROOT / "kit.py")] + list(args)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    )
    return result

def test_cli_lifecycle(tmp_path):
    # Use a temporary DB for the CLI test
    db_path = tmp_path / "cli_test.db"
    
    # In kit.py, we might need to point to this DB. 
    # For now, let's assume kit.py looks for brain.db in .kit/ or uses defaults.
    # Since we can't easily change the DB path via CLI yet (unless implemented), 
    # we'll test the default behavior or mock the environment if possible.
    
    # 1. Learn
    res = run_kit("learn", "--uid", "cli_node", "--content", "CLI test fact", "--importance", "0.7")
    assert res.returncode == 0
    
    # 2. Recall
    res = run_kit("recall", "cli_node")
    assert res.returncode == 0
    assert "CLI test fact" in res.stdout
    
    # 3. Search
    res = run_kit("search", "CLI")
    assert res.returncode == 0
    assert "CLI test fact" in res.stdout

def test_cli_init_creates_brain_and_manifest(tmp_path):
    res = run_kit("init", cwd=tmp_path)

    assert res.returncode == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".kit" / "brain.db").exists()
    assert (tmp_path / "docs" / "reference.md").exists()
    agents_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "Run `kit recall` exactly as written." in agents_text
    assert "Do not replace it with `python kit.py recall`." in agents_text


def test_cli_init_and_recall_work_in_hyphenated_directory(tmp_path):
    project_dir = tmp_path / "Framework Full-Stack"
    project_dir.mkdir()

    init_res = run_kit("init", cwd=project_dir)

    assert init_res.returncode == 0
    assert (project_dir / "AGENTS.md").exists()
    assert (project_dir / ".kit" / "brain.db").exists()
    assert (project_dir / "docs" / "reference.md").exists()

    recall_res = run_kit("recall", cwd=project_dir)

    assert recall_res.returncode == 0
    assert "kit startup begins with kit recall" in recall_res.stdout


def test_preflight_passes_for_small_non_blocking_diff(tmp_path):
    db_path = tmp_path / "preflight_test.db"

    subprocess.run(
        ["python", "-m", "kit.cli.main", "--db", str(db_path), "learn", "--uid", "db", "--tag", "invariant", "--content", "All database operations MUST use SQLite."],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    res = subprocess.run(
        ["python", "-m", "kit.cli.main", "--db", str(db_path), "preflight", "-m", "feat(core): add redis path"],
        input="import redis\ncache = redis.Redis(host='localhost')\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    assert res.returncode == 0
    assert "Cognitive Check:" in res.stdout


def test_doctor_output_is_ascii_safe(tmp_path):
    db_path = tmp_path / "doctor_test.db"

    subprocess.run(
        [
            "python",
            "-m",
            "kit.cli.main",
            "--db",
            str(db_path),
            "learn",
            "--uid",
            "doctor",
            "--tag",
            "invariant",
            "--content",
            "ASCII-safe dashboard output is required on Windows consoles.",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    res = subprocess.run(
        ["python", "-m", "kit.cli.main", "--db", str(db_path), "doctor", "--mode", "safe"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    assert res.returncode == 0
    assert ".KIT COGNITIVE DASHBOARD" in res.stderr
    res.stderr.encode("ascii")
