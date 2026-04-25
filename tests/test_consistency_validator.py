import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from kit.core.consistency_validator import summarize_consistency


def _run_kit(cwd: Path, *args: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.absolute())
    env["KIT_BYPASS_RUNTIME_LOCK"] = "1"
    env["KIT_DISABLE_ASYNC_BAKE"] = "1"
    env["PYTHONUTF8"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "kit", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60.0,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def test_consistency_summary_passes_for_current_layers():
    report = summarize_consistency(
        vantage_capabilities={"binary": "test", "commands": ["graph", "verify-memory"], "ok": True},
        policy_text="", # Isolate from AGENTS.md drift
    )

    assert report["ok"] is True
    assert report["issues"] == []
    assert report["observability"]["self_noise_overlap"] == []


def test_consistency_summary_detects_route_and_policy_drift():
    report = summarize_consistency(
        routes={
            "ghost": {"executor": "fs", "mode": "direct"},
            "graph": {"executor": "vantage", "mode": "direct"},
            "stats": {"executor": "memory", "mode": "routed"},
        },
        cli_surface={"graph": {"options": ["--json"]}},
        registry_commands={"graph"},
        observability_commands={"stats", "trace"},
        policy_text="kit graph\n",
        vantage_capabilities={"binary": "test", "commands": ["graph"], "ok": True},
    )

    issue_kinds = {issue["kind"] for issue in report["issues"]}
    assert "missing_cli_surface" in issue_kinds
    assert "observability_self_noise_overlap" in issue_kinds
    assert "policy_runtime_reference" in issue_kinds
    assert "unsupported_vantage_mapping" in issue_kinds


def test_stats_consistency_works_without_workspace_init(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        monkeypatch.setenv("KIT_GLOBAL_HOME", str(root / "global"))

        rc, stdout, stderr = _run_kit(root, "stats", "--consistency", "--json")
        assert rc == 0, stderr
        report = json.loads(stdout)
        assert "ok" in report
        assert "issues" in report
        assert not (root / ".kit").exists()
