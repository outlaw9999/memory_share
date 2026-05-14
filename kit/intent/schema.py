# kit/intent/schema.py
# v1.2.5 — Intent Schema: Canonical semantic surface for the entire KIT system.
#
# INVARIANT: Runtime never mutates during planning.
#   Normalize → Resolve → Plan → Verify → Execute → Trace
#   No phase may silently mutate state. The plan is constructed *before* any execution.
#   This guarantees replayability, inspectability, and deterministic behavior.

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum, StrEnum
from typing import Any, Optional

# ── Domains & Actions ──────────────────────────────────────────────────────────


class IntentDomain(StrEnum):
    MEMORY = "memory"
    GRAPH = "graph"
    RUNTIME = "runtime"
    VERIFICATION = "verification"
    LIFECYCLE = "lifecycle"
    RELEASE = "release"
    DIAGNOSTIC = "diagnostic"


class IntentAction(StrEnum):
    # Memory
    LEARN = "learn"
    RECALL = "recall"
    RECONCILE = "reconcile"
    MIGRATE = "migrate"
    EVOLVE = "evolve"
    COMPACT = "compact"
    # Graph
    BUILD = "build"
    REBUILD = "rebuild"
    VERIFY = "verify"
    INSPECT = "inspect"
    # Runtime
    HEALTH = "health"
    INTROSPECT = "introspect"
    EXECUTE = "execute"
    # Verification
    VALIDATE = "validate"
    AUDIT = "audit"
    # Lifecycle
    INIT = "init"
    SEAL = "seal"
    UNSEAL = "unseal"
    SNAPSHOT = "snapshot"
    RESTORE = "restore"
    PRE_COMMIT = "pre_commit"
    POST_COMMIT = "post_commit"
    COMMIT = "commit"
    # Release
    TEST = "test"
    RELEASE = "release"
    # Diagnostic
    DOCTOR = "doctor"
    TRACE = "trace"
    METRICS = "metrics"


@dataclass(frozen=True, order=True)
class CanonicalIntent:
    """
    The atomic semantic unit of the system.
    Format: DOMAIN:ACTION (e.g. MEMORY:LEARN, LIFECYCLE:PRE_COMMIT)
    """

    domain: IntentDomain
    action: IntentAction

    def __str__(self) -> str:
        return f"{self.domain.value.upper()}:{self.action.value.upper()}"

    @classmethod
    def from_string(cls, raw: str) -> CanonicalIntent:
        parts = raw.strip().upper().split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid intent format: {raw!r}. Expected DOMAIN:ACTION")
        return cls(domain=IntentDomain(parts[0].lower()), action=IntentAction(parts[1].lower()))


# ── Intent Context (runtime metadata) ─────────────────────────────────────────


class IntentOrigin(StrEnum):
    HOOK = "hook"
    AGENT = "agent"
    MANUAL = "manual"
    API = "api"
    RUNTIME = "runtime"


@dataclass
class IntentContext:
    """Runtime metadata — separated from event-specific payload to prevent concern pollution."""

    caller_id: str
    origin: IntentOrigin
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    execution_depth: int = 0
    replay_mode: bool = False
    dry_run: bool = False
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_trace_id: str | None = None


# ── Intent Payload (event-specific data) ───────────────────────────────────────


@dataclass
class IntentPayload:
    """Event-specific data carried by the intent. Never contains orchestration metadata."""

    intent: CanonicalIntent
    context: IntentContext
    data: dict[str, Any] = field(default_factory=dict)
    git_diff: str | None = None
    branch: str | None = None
    commit_hash: str | None = None
    memory_snapshot_id: str | None = None
    risk_level: float = 0.0


# ── Runtime Trace (observability + replay) ────────────────────────────────────
# Layered architecture (v1.2.5):
#   TraceMetadata      → identity
#   ExecutionLineage   → parent/children
#   MutationLog        → state changes
#   ObservationLog     → logs/events
#   VerdictLog         → policy decisions


class TraceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MutationRecord:
    target: str
    operation: str
    entity_id: str | None = None
    success: bool = True


@dataclass
class VerdictRecord:
    validator: str
    status: str
    confidence: float = 1.0
    reason: str | None = None


@dataclass
class TimestampRecord:
    event: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── Trace Layers ───────────────────────────────────────────────────────────────


@dataclass
class TraceMetadata:
    """Layer 1: Identity — fixed once created."""

    trace_id: str
    status: TraceStatus = TraceStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


@dataclass
class ExecutionLineage:
    """Layer 2: Parent/children relationships for replay and loop detection."""

    intent_chain: list[CanonicalIntent]
    parent_trace_id: str | None = None
    execution_plan_id: str | None = None
    depth: int = 0


@dataclass
class MutationLog:
    """Layer 3: All state mutations performed during intent execution."""

    entries: list[MutationRecord] = field(default_factory=list)


@dataclass
class ObservationLog:
    """Layer 4: Timestamped events for debugging and audit."""

    entries: list[TimestampRecord] = field(default_factory=list)


@dataclass
class VerdictLog:
    """Layer 5: All policy decisions (Vantage, PolicyGuard, etc.)."""

    entries: list[VerdictRecord] = field(default_factory=list)


@dataclass
class RuntimeTrace:
    """Full trace of an intent's lifecycle — foundation for replay, debugging, and observability.
    Invariant: RuntimeTrace is assembled AFTER planning, never mutated during execution."""

    metadata: TraceMetadata
    lineage: ExecutionLineage
    mutations: MutationLog = field(default_factory=MutationLog)
    observations: ObservationLog = field(default_factory=ObservationLog)
    verdicts: VerdictLog = field(default_factory=VerdictLog)

    @classmethod
    def create(
        cls, trace_id: str, intent_chain: list[CanonicalIntent], parent_trace_id: str | None = None
    ) -> RuntimeTrace:
        return cls(
            metadata=TraceMetadata(trace_id=trace_id),
            lineage=ExecutionLineage(
                intent_chain=intent_chain,
                parent_trace_id=parent_trace_id,
                depth=len(intent_chain),
            ),
        )

    def record(self, event: str) -> None:
        self.observations.entries.append(TimestampRecord(event=event))


# ── Runtime Result ─────────────────────────────────────────────────────────────


@dataclass
class IntentResult:
    """Outcome of processing an intent through the runtime.
    === Contract (v1.2.5) ===
    - status:      machine-readable outcome for git hooks
    - trace:       full runtime trace for debugging and replay
    - error:       human-readable error if failed
    - retryable:   whether failure can be safely retried
    - diagnostic:  key-value diagnostics for automation"""

    intent: CanonicalIntent
    trace: RuntimeTrace
    status: TraceStatus
    error: str | None = None
    mutations_applied: int = 0
    verification_status: str | None = None
    retryable: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
