# kit/intent/execution.py
# v1.2.5 — ExecutionIntent: execution semantics between Normalizer and Resolver.
# Normalizer produces IntentPayload (what + who).
# ExecutionIntent enriches with (why, priority, mutability contract) for the Resolver/Planner.

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from kit.intent.schema import (
    CanonicalIntent,
    IntentAction,
    IntentDomain,
    IntentOrigin,
    IntentPayload,
)


class ExecutionSource(StrEnum):
    GIT_HOOK = "git_hook"
    AGENT = "agent"
    MANUAL = "manual"
    REPAIR = "repair"
    BACKGROUND = "background"


class Mutability(StrEnum):
    READONLY = "readonly"
    SAFE_WRITE = "safe_write"
    STRUCTURAL = "structural"


@dataclass
class ExecutionIntent:
    """
    Execution semantics layer — answers WHY this execution exists.
    Sits between Normalizer and Resolver in the pipeline:
      Normalizer → ExecutionIntent → Resolver → Planner → Policy → Execute → Trace
    """

    payload: IntentPayload
    source: ExecutionSource
    goal: str
    priority: int
    mutability: Mutability
    requires_verification: bool
    auto_repair: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: IntentPayload, **overrides) -> ExecutionIntent:
        source = overrides.get("source", _derive_source(payload.context.origin))
        mutability = overrides.get("mutability", _derive_mutability(payload.intent))
        priority = overrides.get("priority", _derive_priority(source))
        goal = overrides.get("goal", _derive_goal(payload.intent))
        requires_verification = overrides.get(
            "requires_verification",
            mutability == Mutability.STRUCTURAL,
        )
        return cls(
            payload=payload,
            source=source,
            goal=goal,
            priority=priority,
            mutability=mutability,
            requires_verification=requires_verification,
            auto_repair=overrides.get("auto_repair", False),
            metadata=overrides.get("metadata", {}),
        )

    @property
    def intent(self) -> CanonicalIntent:
        return self.payload.intent


# ── Derivation Helpers ─────────────────────────────────────────────────────────

_SOURCE_MAP: dict[IntentOrigin, ExecutionSource] = {
    IntentOrigin.HOOK: ExecutionSource.GIT_HOOK,
    IntentOrigin.AGENT: ExecutionSource.AGENT,
    IntentOrigin.MANUAL: ExecutionSource.MANUAL,
    IntentOrigin.API: ExecutionSource.MANUAL,
    IntentOrigin.RUNTIME: ExecutionSource.BACKGROUND,
}

_MUTABILITY_MAP: dict[tuple[IntentDomain, IntentAction], Mutability] = {
    # Read-only
    (IntentDomain.MEMORY, IntentAction.RECALL): Mutability.READONLY,
    (IntentDomain.VERIFICATION, IntentAction.VERIFY): Mutability.READONLY,
    (IntentDomain.VERIFICATION, IntentAction.VALIDATE): Mutability.READONLY,
    (IntentDomain.VERIFICATION, IntentAction.AUDIT): Mutability.READONLY,
    (IntentDomain.DIAGNOSTIC, IntentAction.DOCTOR): Mutability.READONLY,
    (IntentDomain.DIAGNOSTIC, IntentAction.TRACE): Mutability.READONLY,
    (IntentDomain.DIAGNOSTIC, IntentAction.METRICS): Mutability.READONLY,
    (IntentDomain.RUNTIME, IntentAction.HEALTH): Mutability.READONLY,
    (IntentDomain.RUNTIME, IntentAction.INTROSPECT): Mutability.READONLY,
    (IntentDomain.GRAPH, IntentAction.INSPECT): Mutability.READONLY,
    # Safe write (non-structural mutations)
    (IntentDomain.MEMORY, IntentAction.LEARN): Mutability.SAFE_WRITE,
    (IntentDomain.MEMORY, IntentAction.EVOLVE): Mutability.SAFE_WRITE,
    (IntentDomain.MEMORY, IntentAction.RECONCILE): Mutability.SAFE_WRITE,
    (IntentDomain.RUNTIME, IntentAction.EXECUTE): Mutability.SAFE_WRITE,
    (IntentDomain.RELEASE, IntentAction.TEST): Mutability.SAFE_WRITE,
    (IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT): Mutability.SAFE_WRITE,
    (IntentDomain.LIFECYCLE, IntentAction.POST_COMMIT): Mutability.SAFE_WRITE,
    (IntentDomain.LIFECYCLE, IntentAction.COMMIT): Mutability.SAFE_WRITE,
    # Structural (requires verification)
    (IntentDomain.GRAPH, IntentAction.BUILD): Mutability.STRUCTURAL,
    (IntentDomain.GRAPH, IntentAction.REBUILD): Mutability.STRUCTURAL,
    (IntentDomain.MEMORY, IntentAction.MIGRATE): Mutability.STRUCTURAL,
    (IntentDomain.MEMORY, IntentAction.COMPACT): Mutability.STRUCTURAL,
    (IntentDomain.LIFECYCLE, IntentAction.INIT): Mutability.STRUCTURAL,
    (IntentDomain.LIFECYCLE, IntentAction.SEAL): Mutability.STRUCTURAL,
    (IntentDomain.LIFECYCLE, IntentAction.UNSEAL): Mutability.STRUCTURAL,
    (IntentDomain.LIFECYCLE, IntentAction.SNAPSHOT): Mutability.STRUCTURAL,
    (IntentDomain.LIFECYCLE, IntentAction.RESTORE): Mutability.STRUCTURAL,
    (IntentDomain.RELEASE, IntentAction.RELEASE): Mutability.STRUCTURAL,
}

_PRIORITY_MAP: dict[ExecutionSource, int] = {
    ExecutionSource.MANUAL: 100,
    ExecutionSource.REPAIR: 80,
    ExecutionSource.GIT_HOOK: 50,
    ExecutionSource.AGENT: 30,
    ExecutionSource.BACKGROUND: 10,
}

_GOAL_MAP: dict[IntentAction, str] = {
    IntentAction.LEARN: "Record cognitive observation",
    IntentAction.RECALL: "Retrieve context",
    IntentAction.RECONCILE: "Resolve graph after merge",
    IntentAction.MIGRATE: "Upgrade legacy memory path",
    IntentAction.EVOLVE: "Evolve memory topology",
    IntentAction.COMPACT: "Canonicalize and compress memory",
    IntentAction.BUILD: "Build structural graph",
    IntentAction.REBUILD: "Rebuild structural graph",
    IntentAction.VERIFY: "Verify structural integrity",
    IntentAction.INSPECT: "Inspect graph topology",
    IntentAction.HEALTH: "Environment and schema diagnostics",
    IntentAction.INTROSPECT: "Runtime introspection",
    IntentAction.EXECUTE: "Generic execution",
    IntentAction.VALIDATE: "Validate integrity",
    IntentAction.AUDIT: "Full audit",
    IntentAction.INIT: "Initialize kit environment",
    IntentAction.SEAL: "Seal kernel state",
    IntentAction.UNSEAL: "Unseal kernel state",
    IntentAction.SNAPSHOT: "Create memory snapshot",
    IntentAction.RESTORE: "Restore from snapshot",
    IntentAction.PRE_COMMIT: "Pre-commit integrity validation",
    IntentAction.POST_COMMIT: "Post-commit memory update",
    IntentAction.COMMIT: "Git commit lifecycle",
    IntentAction.TEST: "Run release tests",
    IntentAction.RELEASE: "Release gate validation",
    IntentAction.DOCTOR: "System health and repair diagnostics",
    IntentAction.TRACE: "Execution trace inspection",
    IntentAction.METRICS: "System metrics collection",
}


def _derive_source(origin: IntentOrigin) -> ExecutionSource:
    return _SOURCE_MAP.get(origin, ExecutionSource.AGENT)


def _derive_mutability(intent: CanonicalIntent) -> Mutability:
    return _MUTABILITY_MAP.get(
        (intent.domain, intent.action),
        Mutability.READONLY,
    )


def _derive_priority(source: ExecutionSource) -> int:
    return _PRIORITY_MAP.get(source, 30)


def _derive_goal(intent: CanonicalIntent) -> str:
    return _GOAL_MAP.get(intent.action, f"Execute {intent}")
