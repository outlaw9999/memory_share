# kit/vantage/engine.py
# v1.2.5 — EpistemicEngine: deterministic 5-step truth certification pipeline.
#
# This engine does NOT approve memory. It only certifies reality.
# It returns a Verdict (APPROVED/REJECTED/DEGRADED) that the RuntimeEngine
# uses to decide whether to proceed with execution.
#
# Pipeline:
#   Step 1: Structural validation     → schema compliance
#   Step 2: Epistemic consistency     → proposed effect vs invariants
#   Step 3: Causal safety             → recursion / loop / depth hazard
#   Step 4: Idempotency               → fingerprint(request) ∈ recent_cache
#   Step 5: Optional Rust verification → structural hash / cryptographic proof

import time
from typing import Any

from kit.vantage.contract import (
    EventClass,
    IntentClass,
    Proof,
    ProofMode,
    ReasonCode,
    RustFallback,
    Verdict,
    VerdictResult,
    VerificationRequest,
)

_FINGERPRINT_WINDOW = 5.0


class EpistemicEngine:
    """Deterministic epistemic filter. Side-effect free. Stateless (except fingerprint cache)."""

    def __init__(self, rust_bridge: Any = None):
        self._rust = rust_bridge
        self._fingerprints: dict[str, float] = {}

    def verify(self, request: VerificationRequest) -> VerdictResult:
        """Run the full 5-step verification pipeline. Returns a VerdictResult."""

        # Step 1: Structural validation (always runs first)
        violations: list[str] = []
        if not request.event.type:
            violations.append("Missing event type")
        if request.proof_mode == ProofMode.STRICT and not request.context.commit_hash:
            violations.append("Missing commit hash in STRICT mode")

        if violations:
            return VerdictResult(
                verdict=Verdict.REJECTED,
                confidence=0.0,
                reason_code=ReasonCode.SCHEMA_VIOLATION,
                explanation="; ".join(violations),
                proof=Proof(violations=violations, invariants_checked=["structural"]),
            )

        invariants_checked = ["structural"]
        partial_confidence = 1.0

        # Step 2: Epistemic consistency (only for WRITE/VERIFY)
        if request.intent in (IntentClass.WRITE, IntentClass.VERIFY):
            epi_violation = self._check_epistemic_consistency(request)
            if epi_violation:
                violations.append(epi_violation)
                partial_confidence *= 0.5
            invariants_checked.append("epistemic_consistency")

        # Step 3: Causal safety
        causal_violation = self._check_causal_safety(request)
        if causal_violation:
            violations.append(causal_violation)
            partial_confidence *= 0.0  # Hard rejection for safety violations
        invariants_checked.append("causal_safety")

        # Step 4: Idempotency
        idem_violation = self._check_idempotency(request)
        if idem_violation:
            violations.append(idem_violation)
            partial_confidence *= 0.1
        invariants_checked.append("idempotency")

        # Step 5: Optional Rust verification
        rust_result = None
        if self._rust and request.proof_mode == ProofMode.STRICT:
            try:
                rust_result = self._rust.verify(request)
                if rust_result.get("status") == "rejected":
                    violations.append("Rust verification rejected")
                    partial_confidence *= 0.0
                invariants_checked.append("rust_verification")
            except Exception:
                violations.append("Rust verification failed")
                partial_confidence *= 0.5
                invariants_checked.append("rust_verification_error")

        # Determine verdict from violations
        if violations:
            verdict = Verdict.REJECTED if partial_confidence < 0.3 else Verdict.DEGRADED
            reason_code = self._classify_violations(violations)
        else:
            verdict = Verdict.APPROVED
            reason_code = ReasonCode.APPROVED

        return VerdictResult(
            verdict=verdict,
            confidence=round(max(0.0, partial_confidence), 4),
            reason_code=reason_code,
            explanation="; ".join(violations) if violations else "All checks passed",
            proof=Proof(
                violations=violations,
                invariants_checked=invariants_checked,
                structural_hash=rust_result.get("hash", "") if rust_result else "",
            ),
            fallback=RustFallback(
                engaged=self._rust is not None and rust_result is not None,
                confidence=rust_result.get("confidence", 0.0) if rust_result else 0.0,
            ),
        )

    def _check_epistemic_consistency(self, request: VerificationRequest) -> str | None:
        if not request.proposed_effect.memory_delta:
            return None
        delta = request.proposed_effect.memory_delta
        if "write" in delta and not delta.get("source"):
            return "Memory delta missing source provenance"
        if "overwrite" in delta and not delta.get("authorization"):
            return "Overwrite without authorization"
        return None

    def _check_causal_safety(self, request: VerificationRequest) -> str | None:
        if request.context.depth > 3:
            return f"Execution depth {request.context.depth} exceeds safe limit of 3"
        return None

    def _check_idempotency(self, request: VerificationRequest) -> str | None:
        key = f"{request.context.commit_hash}:{request.intent}"
        now = time.monotonic()
        if key in self._fingerprints:
            last = self._fingerprints[key]
            if now - last < _FINGERPRINT_WINDOW:
                return f"Duplicate request: {key} within {_FINGERPRINT_WINDOW}s"
        self._fingerprints[key] = now
        return None

    @staticmethod
    def _classify_violations(violations: list[str]) -> ReasonCode:
        for v in violations:
            vl = v.lower()
            if "schema" in vl or "missing" in vl:
                return ReasonCode.SCHEMA_VIOLATION
            if "invariant" in vl or "provenance" in vl:
                return ReasonCode.INVARIANT_BREAK
            if "loop" in vl or "depth" in vl:
                return ReasonCode.LOOP_RISK
            if "duplicate" in vl:
                return ReasonCode.LOOP_RISK
            if "unverifiable" in vl:
                return ReasonCode.UNVERIFIABLE_STATE
            if "rust" in vl:
                return ReasonCode.RUST_REJECTED
        return ReasonCode.UNKNOWN
