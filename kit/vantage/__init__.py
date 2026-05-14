# kit/vantage/__init__.py
# v1.2.5 — Epistemic Layer (EL-1): truth-gating function inside cognitive substrate.

from kit.vantage.bridge import RustBridge
from kit.vantage.contract import (
    EventClass,
    EventInfo,
    IntentClass,
    Proof,
    ProofMode,
    ProposedEffect,
    ReasonCode,
    RustFallback,
    Verdict,
    VerdictResult,
    VerificationContext,
    VerificationRequest,
)
from kit.vantage.engine import EpistemicEngine

__all__ = [
    "EpistemicEngine",
    "RustBridge",
    "VerificationRequest",
    "VerdictResult",
    "Verdict",
    "IntentClass",
    "EventClass",
    "ProofMode",
    "ReasonCode",
    "VerificationContext",
    "EventInfo",
    "ProposedEffect",
    "Proof",
    "RustFallback",
]
