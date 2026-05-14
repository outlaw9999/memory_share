import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from kit.core.drift_repair import (
    DriftType,
    build_repair_plan,
    render_repair_diff,
    validate_plan_payload,
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


def test_repair_plan_builds_replayable_mechanical_drift():
    report = {
        "issues": [
            {
                "kind": "observability_self_noise_overlap",
                "commands": ["doctor"],
            }
        ]
    }

    plan_document = build_repair_plan(report)
    assert len(plan_document.drifts) == 1
    drift = plan_document.drifts[0]
    assert drift.type == DriftType.MECHANICAL
    assert drift.replayable is True
    assert drift.requires_human is False
    assert drift.patch.startswith("--- ")

    ok, error = validate_plan_payload(plan_document.model_dump(mode="json"))
    assert ok is True, error


def test_repair_diff_renders_only_mechanical_candidates():
    report = {
        "issues": [
            {
                "kind": "observability_self_noise_overlap",
                "commands": ["doctor"],
            },
            {
                "kind": "policy_runtime_reference",
                "lines": ["kit graph"],
            },
        ]
    }

    diff_text = render_repair_diff(build_repair_plan(report))
    assert "OBSERVABILITY_COMMANDS" in diff_text
    assert "kit graph" not in diff_text


def test_repair_plan_command_works_without_workspace_init(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        monkeypatch.setenv("KIT_GLOBAL_HOME", str(root / "global"))

        rc, stdout, stderr = _run_kit(root, "repair", "--plan", "--json")
        assert rc == 0, stderr
        payload = json.loads(stdout)
        assert "drifts" in payload
        assert not (root / ".kit").exists()


def test_repair_apply_requires_confirmation(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        monkeypatch.setenv("KIT_GLOBAL_HOME", str(root / "global"))

        rc, stdout, stderr = _run_kit(root, "repair", "--apply", "--json")
        assert rc == 1
        payload = json.loads(stdout)
        assert payload["reason"] == "confirmation_required"
        assert not (root / ".kit").exists()
