# kit/runtime/policy_guard.py
# v1.2.5 — PolicyGuard: validates execution BEFORE it happens.
# Runs between Planner and Executor. Never mutates external state.
#
# Built-in rules (v1.2.5):
#   depth_limit     — max execution depth = 3
#   storm_prevention — max 3x same intent in 10s
#   fingerprint     — dedup same hook+HEAD within 5s window
#   hook_depth      — max KIT_HOOK_DEPTH = 5

import os
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional

from kit.intent.execution import ExecutionIntent
from kit.runtime.planner import ExecutionPlan


@dataclass
class PlanVerdict:
    approved: bool
    reason: str = ""
    violations: list[str] = field(default_factory=list)


@dataclass
class PolicyRule:
    name: str
    check: Callable[[ExecutionIntent, ExecutionPlan], str | None]


_MAX_EXECUTION_DEPTH = 3
_MAX_HOOK_DEPTH = 5
_STORM_WINDOW = 10.0
_MAX_STORM_COUNT = 3
_FINGERPRINT_WINDOW = 5.0


class PolicyGuard:
    """Validates execution plans and intent context before execution.
    Maintains internal state for storm/recursion detection; never mutates external state."""

    def __init__(self):
        self._rules: list[PolicyRule] = []
        self._recent: deque[tuple] = deque(maxlen=100)
        self._fingerprints: dict[tuple, float] = {}

        self._add_builtins()

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def check(self, execution_intent: ExecutionIntent, plan: ExecutionPlan) -> PlanVerdict:
        violations: list[str] = []
        for rule in self._rules:
            try:
                violation = rule.check(execution_intent, plan)
                if violation:
                    violations.append(violation)
            except Exception as e:
                violations.append(f"{rule.name}: error — {e}")

        # Always record for storm detection
        self._recent.append(
            (
                (execution_intent.intent, execution_intent.source),
                time.monotonic(),
            )
        )

        return PlanVerdict(
            approved=len(violations) == 0,
            reason="; ".join(violations) if violations else "approved",
            violations=violations,
        )

    def _add_builtins(self) -> None:
        self._rules.extend(
            [
                PolicyRule(name="depth_limit", check=_check_depth),
                PolicyRule(name="storm_prevention", check=lambda ei, ep: _check_storm(ei, ep, self._recent)),
                PolicyRule(name="fingerprint", check=lambda ei, ep: _check_fingerprint(ei, ep, self._fingerprints)),
                PolicyRule(name="hook_depth", check=_check_hook_depth),
            ]
        )


# ── Built-in Rule Implementations ──────────────────────────────────────────────


def _check_depth(execution_intent: ExecutionIntent, plan: ExecutionPlan) -> str | None:
    depth = execution_intent.payload.context.execution_depth
    if depth >= _MAX_EXECUTION_DEPTH:
        return f"Execution depth {depth} exceeds limit of {_MAX_EXECUTION_DEPTH}"
    return None


def _check_storm(execution_intent: ExecutionIntent, plan: ExecutionPlan, recent: deque) -> str | None:
    now = time.monotonic()
    fingerprint = (execution_intent.intent, execution_intent.source)
    count = sum(1 for f, t in recent if f == fingerprint and now - t < _STORM_WINDOW)
    if count >= _MAX_STORM_COUNT:
        return f"Hook storm detected: {count + 1}x {execution_intent.intent} in {_STORM_WINDOW}s"
    return None


def _check_fingerprint(execution_intent: ExecutionIntent, plan: ExecutionPlan, fingerprints: dict) -> str | None:
    """Reject if same (caller, intent, commit) executed within dedup window."""
    commit = execution_intent.payload.commit_hash or execution_intent.payload.context.trace_id
    key = (
        execution_intent.payload.context.caller_id,
        execution_intent.intent,
        commit,
    )
    now = time.monotonic()

    if key in fingerprints:
        last = fingerprints[key]
        if now - last < _FINGERPRINT_WINDOW:
            return f"Duplicate execution blocked: {execution_intent.intent} already ran {now - last:.1f}s ago"
    fingerprints[key] = now
    return None


def _check_hook_depth(execution_intent: ExecutionIntent, plan: ExecutionPlan) -> str | None:
    raw = os.environ.get("KIT_HOOK_DEPTH", "0")
    try:
        depth = max(0, int(raw))
    except ValueError, TypeError:
        depth = 0
    if depth > _MAX_HOOK_DEPTH:
        return f"Hook depth {depth} exceeds limit of {_MAX_HOOK_DEPTH}"
    return None
