import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from kit.core.execution_trace import (
    log_execution_event,
    read_execution_events,
    summarize_execution_paths,
    summarize_hot_paths,
)


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


def test_execution_trace_module_aggregates_events(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("KIT_GLOBAL_HOME", str(Path(tmpdir) / "global"))

        log_execution_event("graph", "direct", "dispatch", 1.2, True)
        log_execution_event("graph", "direct", "executor", 12.4, True)
        log_execution_event("recall", "routed", "parser", 4.1, True, "semantic_handler_path")

        events = read_execution_events(limit=10)
        assert len(events) == 3

        summary = summarize_execution_paths(limit=10)
        assert summary["sample_size"] == 3
        assert summary["path_summary"]["direct"]["dispatch"]["count"] == 1
        assert summary["path_summary"]["direct"]["executor"]["count"] == 1
        assert summary["fallback_reasons"]["semantic_handler_path"] == 1


def test_hot_path_summary_ranks_executor_heavy_commands(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("KIT_GLOBAL_HOME", str(Path(tmpdir) / "global"))

        log_execution_event("graph", "direct", "dispatch", 1.0, True)
        log_execution_event("graph", "direct", "executor", 4.0, True)
        log_execution_event("doctor", "diagnostic", "dispatch", 1.5, True)
        log_execution_event("doctor", "diagnostic", "executor", 75.0, True)

        report = summarize_hot_paths(limit=10)
        assert report["sample_size"] == 4
        assert report["hotpaths"][0]["command"] == "doctor"
        assert report["hotpaths"][0]["reasoning_depth_ms"] > report["hotpaths"][1]["reasoning_depth_ms"]


def test_trace_and_stats_paths_work_without_workspace_init(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        monkeypatch.setenv("KIT_GLOBAL_HOME", str(root / "global"))

        log_execution_event("graph", "direct", "dispatch", 1.0, True)
        log_execution_event("graph", "direct", "executor", 9.5, True)

        rc, stdout, stderr = _run_kit(root, "trace", "--json", "--limit", "2")
        assert rc == 0, stderr
        trace_events = json.loads(stdout)
        assert len(trace_events) >= 2
        assert not (root / ".kit").exists()

        rc, stdout, stderr = _run_kit(root, "stats", "--paths", "--json", "--limit", "10")
        assert rc == 0, stderr
        summary = json.loads(stdout)
        assert summary["path_summary"]["direct"]["dispatch"]["count"] >= 1
        assert not (root / ".kit").exists()

        rc, stdout, stderr = _run_kit(root, "stats", "--hotpaths", "--json", "--limit", "10")
        assert rc == 0, stderr
        report = json.loads(stdout)
        assert report["hotpaths"][0]["command"] == "graph"
        assert not (root / ".kit").exists()

        rc, stdout, stderr = _run_kit(root, "stats", "--consistency", "--json")
        assert rc == 0, stderr
        report = json.loads(stdout)
        assert "ok" in report
        assert not (root / ".kit").exists()
