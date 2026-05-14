# kit/vantage/contract.py
# v1.2.5 — Epistemic Layer (EL-1): truth certification contract.
#
# kit-vantage does NOT approve memory. It only certifies reality.
# It is a deterministic epistemic filter inside the cognitive substrate.
# Returns Verdict (APPROVED/REJECTED/DEGRADED) — no memory decisions.
#
# INVARIANTS:
#   - Deterministic: same input → same verdict
#   - Side-effect free: never mutates state
#   - Stateless: no learning, no caching beyond request fingerprint

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from enum import StrEnum
from typing import Any, Optional

# ── Enums ──────────────────────────────────────────────────────────────────────


class Verdict(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEGRADED = "DEGRADED"


class IntentClass(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    VERIFY = "VERIFY"
    SYNC = "SYNC"


class EventClass(StrEnum):
    RAW_GIT = "RawGitEvent"
    INTENT = "IntentEvent"
    RUNTIME = "RuntimeEvent"


class ProofMode(StrEnum):
    STRICT = "STRICT"
    RELAXED = "RELAXED"


class ReasonCode(StrEnum):
    APPROVED = "APPROVED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    INVARIANT_BREAK = "INVARIANT_BREAK"
    LOOP_RISK = "LOOP_RISK"
    UNVERIFIABLE_STATE = "UNVERIFIABLE_STATE"
    RUST_REJECTED = "RUST_REJECTED"
    UNKNOWN = "UNKNOWN"


# ── Input: VerificationRequest ─────────────────────────────────────────────────


@dataclass
class EventInfo:
    type: EventClass = EventClass.RUNTIME
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationContext:
    commit_hash: str = ""
    branch: str = ""
    diff_hash: str = ""
    depth: int = 0
    caller: str = "runtime"


@dataclass
class ProposedEffect:
    memory_delta: dict[str, Any] = field(default_factory=dict)
    graph_delta: dict[str, Any] = field(default_factory=dict)
    side_effects: list[str] = field(default_factory=list)


@dataclass
class VerificationRequest:
    """
    The ONLY valid input to the epistemic gate.
    Submitted by RuntimeEngine before any memory mutation.
    """

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    intent: IntentClass = IntentClass.READ
    event: EventInfo = field(default_factory=EventInfo)
    context: VerificationContext = field(default_factory=VerificationContext)
    proposed_effect: ProposedEffect = field(default_factory=ProposedEffect)
    proof_mode: ProofMode = ProofMode.STRICT

    def to_json(self) -> str:
        import json

        return json.dumps(asdict(self), default=str)


# ── Output: VerdictResult ─────────────────────────────────────────────────────


@dataclass
class Proof:
    structural_hash: str = ""
    violations: list[str] = field(default_factory=list)
    invariants_checked: list[str] = field(default_factory=list)


@dataclass
class RustFallback:
    engaged: bool = False
    confidence: float = 0.0


@dataclass
class VerdictResult:
    """
    The ONLY valid output of the epistemic gate.
    Returned to RuntimeEngine — determines whether execution proceeds.
    """

    verdict: Verdict
    confidence: float
    reason_code: ReasonCode
    explanation: str = ""
    proof: Proof = field(default_factory=Proof)
    fallback: RustFallback = field(default_factory=RustFallback)

    @property
    def approved(self) -> bool:
        return self.verdict in (Verdict.APPROVED, Verdict.DEGRADED)

    def to_json(self) -> str:
        import json

        return json.dumps(asdict(self), default=str)
