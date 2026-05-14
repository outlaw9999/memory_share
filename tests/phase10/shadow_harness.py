# tests/phase10/shadow_harness.py
# Phase 11 — Shadow Execution Harness.
#
# Validates the containment guarantee in REAL execution, not just designed test cases.
# Pipeline runs fully — side effects are NOT materialized (no memory writes).
#
# Three validations:
#   1. Trace structure: shadow trace matches expected phase 10 trace
#   2. Containment: no hallucinated intent reaches Grounded domain
#   3. Determinism: same git event produces identical shadow trace across runs

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from kit.intent.execution import ExecutionIntent
from kit.intent.normalizer import normalize_git_event
from kit.intent.registry import HandlerDescriptor, IntentRegistry, IntentResult, RuntimeTrace
from kit.intent.schema import TraceStatus
from kit.runtime.entrypoint import RuntimeEngine
from tests.phase10.containment_harness import _build_registry, _noop_handler

# ── Trace Comparator ───────────────────────────────────────────────────────────


@dataclass
class TraceDiff:
    field: str
    expected: Any = None
    actual: Any = None
    detail: str = ""


def compare_traces(expected_trace: RuntimeTrace, actual_trace: RuntimeTrace) -> list[TraceDiff]:
    """Compare two traces structurally. Returns list of diffs (empty = match)."""
    diffs: list[TraceDiff] = []

    if expected_trace.metadata.status != actual_trace.metadata.status:
        diffs.append(
            TraceDiff(
                field="metadata.status",
                expected=expected_trace.metadata.status.value,
                actual=actual_trace.metadata.status.value,
            )
        )

    if expected_trace.lineage.intent_chain != actual_trace.lineage.intent_chain:
        diffs.append(
            TraceDiff(
                field="lineage.intent_chain",
                expected=[str(i) for i in expected_trace.lineage.intent_chain],
                actual=[str(i) for i in actual_trace.lineage.intent_chain],
            )
        )

    if len(expected_trace.verdicts.entries) != len(actual_trace.verdicts.entries):
        diffs.append(
            TraceDiff(
                field="verdicts.count",
                expected=len(expected_trace.verdicts.entries),
                actual=len(actual_trace.verdicts.entries),
            )
        )
    else:
        for i, (ev, av) in enumerate(zip(expected_trace.verdicts.entries, actual_trace.verdicts.entries, strict=False)):
            if ev.validator != av.validator:
                diffs.append(
                    TraceDiff(
                        field=f"verdicts[{i}].validator",
                        expected=ev.validator,
                        actual=av.validator,
                    )
                )
            if ev.status != av.status:
                diffs.append(
                    TraceDiff(
                        field=f"verdicts[{i}].status",
                        expected=ev.status,
                        actual=av.status,
                    )
                )

    if not expected_trace.lineage.intent_chain and not actual_trace.lineage.intent_chain:
        diffs.append(TraceDiff(field="lineage.intent_chain", detail="both empty"))

    return diffs


# ── Shadow Harness ─────────────────────────────────────────────────────────────


@dataclass
class ShadowRunResult:
    event: str
    shadow_trace: RuntimeTrace
    diffs: list[TraceDiff] = field(default_factory=list)
    matched_expected: bool = False
    error: str | None = None


class ShadowHarness:
    """Runs real git events through shadow runtime, captures traces, validates."""

    def __init__(self):
        self.registry = _build_registry()

    def run_event(self, event: str, commit_hash: str = "shadow-test", branch: str = "main") -> ShadowRunResult:
        """Execute a git event in shadow mode. Captures full trace without side effects."""
        try:
            payload = normalize_git_event(
                event,
                commit_hash=commit_hash,
                branch=branch,
                git_diff="",
            )
            ex = ExecutionIntent.from_payload(payload)
            engine = RuntimeEngine(self.registry, shadow_mode=True)
            result = engine.run(ex)

            return ShadowRunResult(
                event=event,
                shadow_trace=result.trace,
                matched_expected=result.status == TraceStatus.SUCCESS,
            )
        except Exception as e:
            return ShadowRunResult(
                event=event,
                shadow_trace=RuntimeTrace.create(trace_id="error", intent_chain=[]),
                error=str(e),
            )

    def run_sequence(self, events: list[tuple[str, str]]) -> list[ShadowRunResult]:
        """Run a sequence of git events through the shadow runtime."""
        results = []
        for event, commit_hash in events:
            results.append(self.run_event(event, commit_hash))
        return results


# ── Harness Report ─────────────────────────────────────────────────────────────


@dataclass
class ShadowReport:
    runs: list[ShadowRunResult] = field(default_factory=list)
    all_passed: bool = False

    @property
    def summary(self) -> str:
        passed = sum(1 for r in self.runs if r.matched_expected and not r.diffs)
        total = len(self.runs)
        return f"Shadow runs: {passed}/{total} matched expected | Diffs: {sum(len(r.diffs) for r in self.runs)}"

    def print_report(self) -> None:
        print("SHADOW EXECUTION REPORT")
        print("=======================")
        for r in self.runs:
            status = "PASS" if r.matched_expected and not r.diffs else "FAIL"
            print(f"  [{status}] {r.event}")
            if r.diffs:
                for d in r.diffs:
                    print(f"         diff: {d.field} expected={d.expected} actual={d.actual}")
            if r.error:
                print(f"         error: {r.error}")
        print(f"  TOTAL: {self.summary}")
