# kit/runtime/entrypoint.py
# v1.2.5 — RuntimeEngine: single execution gate for ALL side effects.
# Pipeline: Resolve → Plan → Guard → Execute → Trace
# INVARIANT: All state mutations pass through _execute_step. No hidden writes.

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict

from kit.event.contract import RawGitEvent, idempotency_key
from kit.intent.execution import ExecutionIntent
from kit.intent.normalizer import normalize_git_event
from kit.intent.registry import HandlerDescriptor, IntentRegistry
from kit.intent.schema import (
    CanonicalIntent,
    IntentAction,
    IntentDomain,
    IntentResult,
    RuntimeTrace,
    TraceStatus,
    VerdictRecord,
)
from kit.runtime.planner import Planner, StepResult
from kit.runtime.policy_guard import PolicyGuard
from kit.runtime.resolver import Resolver
from kit.vantage.contract import (
    EventClass,
    EventInfo,
    IntentClass,
    ProofMode,
    ProposedEffect,
    VerificationContext,
    VerificationRequest,
)
from kit.vantage.engine import EpistemicEngine

logger = logging.getLogger("kit.runtime.engine")


class RuntimeEngine:
    """Single execution gate for the entire KIT runtime."""

    def __init__(
        self,
        registry: IntentRegistry,
        guard: PolicyGuard | None = None,
        epistemic: EpistemicEngine | None = None,
        shadow_mode: bool = False,
    ):
        self._registry = registry
        self._resolver = Resolver(registry)
        self._planner = Planner()
        self._guard = guard or PolicyGuard()
        self._epistemic = epistemic
        self._shadow_mode = shadow_mode  # If True, pipeline runs but side effects are skipped

    def run(self, execution_intent: ExecutionIntent) -> IntentResult:
        trace = RuntimeTrace.create(
            trace_id=execution_intent.payload.context.trace_id,
            intent_chain=[execution_intent.intent],
            parent_trace_id=execution_intent.payload.context.parent_trace_id,
        )
        trace.record("runtime_started")

        try:
            resolved = self._resolver.resolve(execution_intent)
            trace.record("resolved")

            plan = self._planner.plan(resolved, execution_intent.payload.context)
            trace.record("planned")

            # Epistemic gate: truth validation before execution (Plane 2 boundary)
            if self._epistemic:
                epi_request = VerificationRequest(
                    intent=IntentClass.WRITE if execution_intent.mutability.value != "readonly" else IntentClass.READ,
                    event=EventInfo(type=EventClass.RUNTIME),
                    context=VerificationContext(
                        commit_hash=execution_intent.payload.commit_hash or "",
                        branch=execution_intent.payload.branch or "",
                        depth=execution_intent.payload.context.execution_depth,
                        caller=execution_intent.source.value,
                    ),
                    proposed_effect=ProposedEffect(
                        memory_delta={},
                        side_effects=[str(execution_intent.intent)],
                    ),
                    proof_mode=ProofMode.STRICT
                    if execution_intent.mutability.value == "structural"
                    else ProofMode.RELAXED,
                )
                epi_result = self._epistemic.verify(epi_request)
                trace.verdicts.entries.append(
                    VerdictRecord(
                        validator="kit-vantage",
                        status=epi_result.verdict.value,
                        reason=epi_result.explanation,
                    )
                )
                if not epi_result.approved:
                    trace.metadata.status = TraceStatus.FAILED
                    trace.record("rejected_by_epistemic_gate")
                    return self._build_result(
                        execution_intent,
                        trace,
                        error=f"Epistemic gate: {epi_result.reason_code.value} — {epi_result.explanation}",
                    )
                trace.record("epistemic_approved")

            verdict = self._guard.check(execution_intent, plan)
            verdict_entry = VerdictRecord(
                validator="policy_guard",
                status="approved" if verdict.approved else "rejected",
                reason=verdict.reason,
            )
            trace.verdicts.entries.append(verdict_entry)

            if not verdict.approved:
                trace.metadata.status = TraceStatus.FAILED
                trace.record("rejected_by_policy")
                return self._build_result(execution_intent, trace, error=verdict.reason)

            trace.record("policy_approved")

            if self._shadow_mode:
                # Shadow mode: record step traces without side effects
                for step in plan.steps:
                    trace.record(f"step_{step.order}_shadow_ok")
                    trace.mutations.entries = trace.mutations.entries  # no-op
                trace.metadata.status = TraceStatus.SUCCESS
                trace.record("shadow_completed")
                return self._build_result(execution_intent, trace, diagnostics_extra={"shadow": True})
            else:
                for step in plan.steps:
                    step_result = self._execute_step(step, execution_intent)
                    tag = "ok" if step_result.success else "fail"
                    trace.record(f"step_{step.order}_{tag}")
                    if not step_result.success:
                        trace.metadata.status = TraceStatus.FAILED
                        return self._build_result(
                            execution_intent,
                            trace,
                            error=step_result.error,
                            retryable=True,
                        )

            trace.metadata.status = TraceStatus.SUCCESS
            trace.record("runtime_completed")
            return self._build_result(execution_intent, trace)

        except Exception as e:
            logger.exception("Runtime error processing %s", execution_intent.intent)
            trace.metadata.status = TraceStatus.FAILED
            trace.record("runtime_error")
            return self._build_result(execution_intent, trace, error=str(e), retryable=False)

    def _build_result(
        self,
        execution_intent: ExecutionIntent,
        trace: RuntimeTrace,
        error: str | None = None,
        retryable: bool = False,
        diagnostics_extra: dict | None = None,
    ) -> IntentResult:
        return IntentResult(
            intent=execution_intent.intent,
            trace=trace,
            status=trace.metadata.status,
            error=error,
            mutations_applied=len(trace.mutations.entries),
            verification_status=_extract_verdict(trace),
            retryable=retryable,
            diagnostics={
                "origin": execution_intent.source.value,
                "mutability": execution_intent.mutability.value,
                "steps": len(trace.lineage.intent_chain),
                **(diagnostics_extra or {}),
            },
        )

    def _execute_step(self, step, execution_intent: ExecutionIntent) -> StepResult:
        """Single execution gate — all side effects route through here."""
        desc = self._registry.resolve(execution_intent.intent)
        if desc is None:
            return StepResult(step=step, success=False, error=f"No handler for {step.action}")

        timeout = (desc.timeout_ms or _STEP_TIMEOUT_MS) / 1000
        start = time.monotonic()
        try:
            result = desc.handler(execution_intent.payload)
            duration = (time.monotonic() - start) * 1000
            if duration > timeout * 1000:
                return StepResult(
                    step=step,
                    success=False,
                    error=f"Step timed out after {duration:.0f}ms",
                    duration_ms=duration,
                )
            return StepResult(
                step=step,
                success=result.status == TraceStatus.SUCCESS,
                error=result.error,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            return StepResult(step=step, success=False, error=str(e), duration_ms=duration)


def _extract_verdict(trace: RuntimeTrace) -> str | None:
    """Extract the most recent verification status from the trace."""
    if not trace.verdicts.entries:
        return None
    return trace.verdicts.entries[-1].status


# ── Default No-Op Handlers ─────────────────────────────────────────────────────
#
# These are placeholders so git hooks work immediately.
# Real handlers (Phase 4+) replace these via IntentRegistry.register().


_STEP_TIMEOUT_MS = 10_000  # 10s max per step


def _noop_handler(payload):
    """Placeholder handler — returns SUCCESS without side effects."""
    ci = payload.intent
    trace = RuntimeTrace.create(trace_id=payload.context.trace_id, intent_chain=[ci])
    trace.metadata.status = TraceStatus.SUCCESS
    return IntentResult(intent=ci, trace=trace, status=TraceStatus.SUCCESS)


_HOOK_DEFAULTS: dict[str, CanonicalIntent] = {
    "pre-commit": CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT),
    "post-commit": CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.POST_COMMIT),
    "post-merge": CanonicalIntent(IntentDomain.MEMORY, IntentAction.RECONCILE),
}


def _build_hook_registry() -> IntentRegistry:
    """Create registry with no-op handlers for git hook intents."""
    reg = IntentRegistry()
    desc = HandlerDescriptor(handler=_noop_handler, side_effects=False)
    for intent in _HOOK_DEFAULTS.values():
        reg.register(intent, _noop_handler, desc)
    return reg


# ── CLI entry point ────────────────────────────────────────────────────────────
#
# DESIGN INVARIANT: Runtime is synchronous by design.
#   No background execution. No concurrent mutation.
#   Single-process, single-thread, deterministic.
#   This guarantees replayability, testability, and debuggability.


def main() -> None:
    """
    CLI entry point for kit-runtime.

    Canonical (Plane 1 → Plane 2 boundary):
        cat event.json | kit-runtime runtime --event -

    Legacy adapter (Plane 1 env vars → Plane 2):
        kit-runtime runtime --hook pre-commit --json
    """
    # Safety: increment hook depth for loop prevention
    current_depth = int(os.environ.get("KIT_HOOK_DEPTH", "0"))
    os.environ["KIT_HOOK_DEPTH"] = str(current_depth + 1)

    parser = argparse.ArgumentParser(prog="kit-runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    runtime_cmd = sub.add_parser("runtime", help="Process a runtime event")
    runtime_cmd.add_argument("--hook", help="Git hook event name (legacy adapter)")
    runtime_cmd.add_argument("--event", help="RawGitEvent JSON path ('-' for stdin)")
    runtime_cmd.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.command == "runtime":
        # ── Ingest from Plane 1 ──────────────────────────────────────────────
        if args.event:
            raw = _read_event(args.event)
            payload = normalize_git_event(raw.event, **asdict(raw.payload))
        elif args.hook:
            raw = RawGitEvent.from_env(args.hook)
            payload = normalize_git_event(
                args.hook,
                git_diff=raw.payload.diff or "",
                commit_hash=raw.payload.commit_hash or "",
                branch=raw.payload.branch or "",
            )
        else:
            parser.error("Either --event or --hook is required")

        ex = ExecutionIntent.from_payload(payload)
        engine = RuntimeEngine(_build_hook_registry())
        result = engine.run(ex)

        if args.json:
            print(
                json.dumps(
                    {
                        "status": result.status.value,
                        "intent": str(result.intent),
                        "trace_id": result.trace.metadata.trace_id,
                        "error": result.error,
                        "verification": result.verification_status,
                        "retryable": result.retryable,
                    }
                )
            )
        else:
            print(f"[kit-runtime] {result.status.value} — {result.intent}")
            if result.error:
                print(f"[kit-runtime] Error: {result.error}")

        sys.exit(0 if result.status == TraceStatus.SUCCESS else 1)


def _read_event(path: str) -> RawGitEvent:
    """Read a RawGitEvent from a file path or stdin ('-')."""
    if path == "-":
        return RawGitEvent.from_stdin()
    with open(path) as f:
        return RawGitEvent.from_json(f.read())


if __name__ == "__main__":
    main()
