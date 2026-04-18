import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cmd(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """v1.2.4-LOCK: Uses canonical entrypoint `python -m kit`."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_golden_path_blocks_invariant_violation(tmp_path: Path) -> None:
    db_path = tmp_path / "golden_path.db"

    init_res = run_cmd(tmp_path, "-m", "kit", "--db", str(db_path), "init")
    assert init_res.returncode == 0

    learn_res = run_cmd(
        tmp_path,
        "-m",
        "kit",
        "--db",
        str(db_path),
        "learn",
        "--uid",
        "auth_policy",
        "--tag",
        "invariant",
        "--content",
        "Auth tokens MUST NOT be logged to console.",
    )
    assert learn_res.returncode == 0

    ask_res = run_cmd(
        tmp_path,
        "-m",
        "kit_agent.cli.main",
        "--db",
        str(db_path),
        "ask",
        "Implement a login logger.",
        "--provider",
        "semantic_mock",
        "--json",
    )
    assert ask_res.returncode == 0

    payload = json.loads(ask_res.stdout)
    assert payload["decision"] == "BLOCK"
    assert "auth tokens" in payload["reason"].lower() or "logged" in payload["reason"].lower()
