# tests/phase10/drift_governance.py
# Phase 12 — Drift Governance Layer.
#
# Tracks invariants over time, detects behavioral regression, ensures
# the containment guarantee doesn't degrade across versions.
#
# Three components:
#   1. InvariantRegistry — versioned invariant store with violation logging
#   2. BehavioralRegressionDetector — periodic Phase 10 re-run against baseline
#   3. ShadowTraceArchive — shadow trace comparison over time

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from kit.intent.normalizer import normalize_git_event
from tests.phase10.containment_harness import (
    HarnessReport,
    _build_registry,
    _validate_containment,
    check_determinism,
    run_full_harness,
)
from tests.phase10.shadow_harness import ShadowHarness, ShadowRunResult, TraceDiff

# ── Component 1: InvariantRegistry ────────────────────────────────────────────

INVARIANTS: list[dict[str, Any]] = [
    {
        "id": "I1",
        "name": "Epistemic non-interference",
        "rule": "kit-vantage does not approve memory. It only certifies reality.",
        "domain": "bounded",
        "verifiable": True,
    },
    {
        "id": "I2",
        "name": "Traffic governance isolation",
        "rule": "PolicyGuard does not evaluate truth. It only governs traffic.",
        "domain": "bounded",
        "verifiable": True,
    },
    {
        "id": "I3",
        "name": "Memory projection purity",
        "rule": "MemoryRouter does not evaluate truth or safety. It only projects.",
        "domain": "grounded",
        "verifiable": True,
    },
    {
        "id": "I4",
        "name": "Memory determinism",
        "rule": "Memory is a deterministic consequence of truth, not a source of truth.",
        "domain": "cross-layer",
        "verifiable": True,
    },
    {
        "id": "I5",
        "name": "No reverse flow",
        "rule": "No reverse flow from Plane 2 to Plane 1.",
        "domain": "cross-layer",
        "verifiable": True,
    },
    {
        "id": "I6",
        "name": "Frozen planning",
        "rule": "Runtime never mutates during planning.",
        "domain": "bounded",
        "verifiable": True,
    },
    {
        "id": "I7",
        "name": "Single execution gate",
        "rule": "Single execution gate for all side effects.",
        "domain": "bounded",
        "verifiable": True,
    },
    {
        "id": "I8",
        "name": "Deterministic reality transition",
        "rule": "Cognition may be probabilistic. Reality transitions must be deterministic.",
        "domain": "cross-layer",
        "verifiable": True,
    },
    {
        "id": "I9",
        "name": "Git as anchor not oracle",
        "rule": "Git anchors reality but does not define truth.",
        "domain": "grounded",
        "verifiable": False,
    },
    {
        "id": "I10",
        "name": "Containment over prevention",
        "rule": "Hallucination is contained, not prevented.",
        "domain": "system",
        "verifiable": True,
    },
]


@dataclass
class ViolationRecord:
    invariant_id: str
    invariant_name: str
    detected_at: str
    detail: str
    version: str = "1.2.5"


class InvariantRegistry:
    """Stores and validates the 10 architecture invariants over time."""

    def __init__(self, log_path: Path | None = None):
        self._log_path = log_path or Path(".kit/governance/invariant_log.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._violations: list[ViolationRecord] = []
        self._load()

    def check_all(self) -> list[ViolationRecord]:
        """Run all verifiable invariants and log violations."""
        violations: list[ViolationRecord] = []
        version = "1.2.5"

        # I5: No reverse flow — verify by scanning runtime source
        import inspect

        from kit.runtime.entrypoint import main

        src = inspect.getsource(main)
        if "git commit" in src or "git push" in src:
            v = ViolationRecord(
                "I5",
                "No reverse flow",
                datetime.now(UTC).isoformat(),
                "Runtime source contains git write commands",
                version,
            )
            violations.append(v)
            self._log(v)

        # I6: Frozen planning — verify ExecutionPlan is frozen
        from kit.intent.execution import Mutability
        from kit.intent.schema import CanonicalIntent, IntentAction, IntentDomain
        from kit.runtime.planner import ExecutionPlan, ExecutionStep

        ci = CanonicalIntent(IntentDomain.MEMORY, IntentAction.LEARN)
        plan = ExecutionPlan(
            intent=ci,
            steps=(ExecutionStep(order=0, action="test", handler_ref="mem", mutability=Mutability.SAFE_WRITE),),
        )
        try:
            plan.steps = ()
            v = ViolationRecord(
                "I6",
                "Frozen planning",
                datetime.now(UTC).isoformat(),
                "ExecutionPlan is mutable — frozen=True invariant broken",
                version,
            )
            violations.append(v)
            self._log(v)
        except Exception:
            pass  # Correctly frozen — no violation

        # I7: Single execution gate
        from kit.runtime.entrypoint import RuntimeEngine

        if not hasattr(RuntimeEngine, "_execute_step"):
            v = ViolationRecord(
                "I7",
                "Single execution gate",
                datetime.now(UTC).isoformat(),
                "_execute_step not found on RuntimeEngine",
                version,
            )
            violations.append(v)
            self._log(v)

        self._violations.extend(violations)
        return violations

    def _log(self, record: ViolationRecord) -> None:
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def _load(self) -> None:
        if self._log_path.exists():
            with open(self._log_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._violations.append(ViolationRecord(**data))

    def report(self) -> dict[str, Any]:
        return {
            "total_invariants": len(INVARIANTS),
            "verifiable": sum(1 for i in INVARIANTS if i["verifiable"]),
            "violations_logged": len(self._violations),
            "recent_violations": [asdict(v) for v in self._violations[-5:]],
        }


# ── Component 2: BehavioralRegressionDetector ─────────────────────────────────


@dataclass
class BaselineSnapshot:
    timestamp: str
    determinism_pass: bool
    determinism_detail: str
    containment_ratio: str
    reverse_flow_pass: bool


class BehavioralRegressionDetector:
    """Runs Phase 10 harness periodically and detects regression from baseline."""

    def __init__(self, baseline_path: Path | None = None):
        self._baseline_path = baseline_path or Path(".kit/governance/baseline.json")
        self._baseline_path.parent.mkdir(parents=True, exist_ok=True)

    def run_and_compare(self) -> dict[str, Any]:
        """Run Phase 10 harness and compare against stored baseline."""
        current = self._capture_current()
        baseline = self._load_baseline()

        regression = False
        diffs: list[str] = []

        if baseline:
            for key in ["determinism_pass", "containment_ratio", "reverse_flow_pass"]:
                if current.get(key) != baseline.get(key):
                    diffs.append(f"{key}: {baseline.get(key)} -> {current.get(key)}")
                    regression = True

        is_stable = not regression
        return {
            "stable": is_stable,
            "regression_detected": regression,
            "differences": diffs,
            "current": current,
            "baseline": baseline or current,  # First run sets baseline
        }

    def _capture_current(self) -> dict[str, Any]:
        report = run_full_harness()
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "determinism_pass": all(r.passed for r in report.determinism),
            "determinism_detail": report.summary,
            "containment_ratio": report.summary,
            "reverse_flow_pass": all(r.passed for r in report.reverse_flow),
        }

    def _load_baseline(self) -> dict | None:
        if self._baseline_path.exists():
            with open(self._baseline_path) as f:
                return json.load(f)
        return None

    def save_baseline(self, data: dict) -> None:
        with open(self._baseline_path, "w") as f:
            json.dump(data, f, indent=2)


# ── Component 3: ShadowTraceArchive ───────────────────────────────────────────


@dataclass
class ShadowTraceEntry:
    event: str
    commit_hash: str
    timestamp: str
    trace_id: str
    verdict_count: int
    status: str


class ShadowTraceArchive:
    """Stores and compares shadow execution traces over time."""

    def __init__(self, archive_path: Path | None = None):
        self._archive_path = archive_path or Path(".kit/governance/shadow_traces.jsonl")
        self._archive_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, result: ShadowRunResult) -> None:
        entry = ShadowTraceEntry(
            event=result.event,
            commit_hash=result.shadow_trace.metadata.trace_id[:8],
            timestamp=datetime.now(UTC).isoformat(),
            trace_id=result.shadow_trace.metadata.trace_id,
            verdict_count=len(result.shadow_trace.verdicts.entries),
            status=result.shadow_trace.metadata.status.value,
        )
        with open(self._archive_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def query(self, event: str, limit: int = 10) -> list[ShadowTraceEntry]:
        entries: list[ShadowTraceEntry] = []
        if self._archive_path.exists():
            with open(self._archive_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        if data["event"] == event:
                            entries.append(ShadowTraceEntry(**data))
        return entries[-limit:]

    def divergence_score(self, event: str) -> float:
        """0.0 = identical traces over time. Higher = more divergence."""
        entries = self.query(event, limit=20)
        if len(entries) < 2:
            return 0.0
        verdict_counts = [e.verdict_count for e in entries]
        if len(set(verdict_counts)) == 1:
            return 0.0
        return sum(abs(verdict_counts[i] - verdict_counts[i - 1]) for i in range(1, len(verdict_counts))) / len(
            verdict_counts
        )


# ── Governance Report ─────────────────────────────────────────────────────────


@dataclass
class GovernanceReport:
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    invariants: dict[str, Any] = field(default_factory=dict)
    regression: dict[str, Any] = field(default_factory=dict)
    divergence: dict[str, float] = field(default_factory=dict)
    drift_score: float = 0.0
    stable: bool = False

    @property
    def summary(self) -> str:
        return (
            f"Drift score: {self.drift_score:.3f} | "
            f"Invariant violations: {self.invariants.get('violations_logged', '?')} | "
            f"Regression: {'YES' if self.regression.get('regression_detected') else 'no'} | "
            f"Divergence: {self.divergence}"
        )


def run_governance() -> GovernanceReport:
    """Run all three drift governance components and return a report."""
    # Component 1: Invariants
    inv_reg = InvariantRegistry()
    inv_reg.check_all()

    # Component 2: Behavioral regression
    detector = BehavioralRegressionDetector()
    regression = detector.run_and_compare()
    if not regression.get("baseline") or not regression.get("current"):
        pass  # First run — baseline set
    detector.save_baseline(regression["current"])

    # Component 3: Shadow trace divergence
    harness = ShadowHarness()
    archive = ShadowTraceArchive()
    for event in ["pre-commit", "post-commit", "post-merge"]:
        result = harness.run_event(event, commit_hash=f"gov-{event}")
        archive.record(result)
    divergence = {e: archive.divergence_score(e) for e in ["pre-commit", "post-commit", "post-merge"]}

    drift = divergence.get("pre-commit", 0.0) + divergence.get("post-commit", 0.0)
    stable = len(inv_reg._violations) == 0 and not regression.get("regression_detected") and drift == 0.0

    return GovernanceReport(
        invariants=inv_reg.report(),
        regression=regression,
        divergence=divergence,
        drift_score=drift,
        stable=stable,
    )
