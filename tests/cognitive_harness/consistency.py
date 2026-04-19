"""
VantageConsistencyChecker - Ensure vantage signals don't drift.

v1.2.4: Validates that:
- kit learn triggers friction properly (not spam)
- reflect doesn't create noise (duplicate observations)
- signal confidence scores are stable
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SignalDrift:
    """Represents a signal drift event."""
    signal_id: str
    old_hash: str
    new_hash: str
    timestamp: float
    severity: str = "warning"


@dataclass
class ConsistencyReport:
    """Report of consistency checks."""
    checks_passed: int = 0
    checks_failed: int = 0
    drifts: list[SignalDrift] = field(default_factory=list)
    friction_triggers: list = field(default_factory=list)
    noise_detected: list = field(default_factory=list)


class VantageConsistencyChecker:
    """
    Check vantage signals for consistency.

    Validates:
    1. Friction triggers at correct times (not spam)
    2. No duplicate observations from reflect
    3. Signal confidence scores are stable
    """

    FRICTION_COOLDOWN_SECONDS = 10.0
    NOISE_SIMILARITY_THRESHOLD = 0.9

    def __init__(self, brain):
        self.brain = brain
        self._last_friction_time: float = 0
        self._friction_history: list = []
        self._observation_signatures: dict = {}

    def check_friction_trigger(
        self,
        signal: str,
        reason: str,
    ) -> tuple[bool, str]:
        """
        Verify friction is triggered appropriately.

        Returns (is_valid, message).
        """
        current_time = time.time()
        time_since_last = current_time - self._last_friction_time

        is_valid = time_since_last >= self.FRICTION_COOLDOWN_SECONDS or self._last_friction_time == 0

        if not is_valid:
            msg = f"FRICTION SPAM detected: {signal} triggered {time_since_last:.1f}s after last (cooldown: {self.FRICTION_COOLDOWN_SECONDS}s)"
            return False, msg

        self._last_friction_time = current_time
        self._friction_history.append({
            "signal": signal,
            "reason": reason,
            "timestamp": current_time,
        })

        return True, f"Friction triggered appropriately for {signal}"

    def check_reflect_noise(
        self,
        observations: list,
        diff_text: str,
    ) -> list[str]:
        """
        Check if reflect creates noise (duplicate observations).

        Returns list of noise signals.
        """
        noise = []
        current_signatures = set()

        for obs in observations:
            sig = self._normalize_observation(obs)
            if sig in current_signatures:
                noise.append(f"NOISE: Duplicate observation for {obs.get('uid', 'unknown')}")
            current_signatures.add(sig)

            if sig in self._observation_signatures:
                old_ts = self._observation_signatures[sig]
                if time.time() - old_ts < 1.0:
                    noise.append(f"NOISE: Rapid re-observation for {obs.get('uid', 'unknown')}")

            self._observation_signatures[sig] = time.time()

        return noise

    def _normalize_observation(self, obs: dict) -> str:
        """Create normalized signature for observation."""
        parts = [
            obs.get("uid", ""),
            obs.get("content", ""),
            obs.get("tag", ""),
        ]
        return json.dumps(parts, sort_keys=True)

    def check_signal_stability(
        self,
        symbol: str,
        old_hash: Optional[str],
        new_hash: str,
    ) -> Optional[SignalDrift]:
        """
        Check if signal hash is stable.

        Returns SignalDrift if drift detected, None otherwise.
        """
        if old_hash is None:
            return None

        if old_hash != new_hash:
            return SignalDrift(
                signal_id=symbol,
                old_hash=old_hash,
                new_hash=new_hash,
                timestamp=time.time(),
                severity="warning",
            )

        return None

    def verify_no_duplicate_signals(
        self,
        signals: list,
    ) -> tuple[bool, str]:
        """
        Verify no duplicate signal UIDs.

        Returns (is_valid, message).
        """
        uids = [s.get("uid") or s.get("symbol") for s in signals if s.get("uid") or s.get("symbol")]
        unique_uids = set(uids)

        if len(uids) != len(unique_uids):
            duplicates = [u for u in unique_uids if uids.count(u) > 1]
            return False, f"Duplicate signals detected: {duplicates}"

        return True, f"All {len(unique_uids)} signals are unique"

    def run_consistency_check(
        self,
        test_name: str,
    ) -> ConsistencyReport:
        """Run full consistency check."""
        report = ConsistencyReport()

        with self.brain.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, uid, content, tag, created_at, structural_hash
                FROM observations
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall()

            observation_list = [dict(row) for row in rows]

            noise = self.check_reflect_noise(observation_list, "")
            report.noise_detected = noise

            report.checks_passed = 1
            if noise:
                report.checks_failed = 1

        return report


class SignalValidator:
    """Validate signal schemas."""

    REQUIRED_FIELDS = ["uid", "confidence", "line", "source"]
    OPTIONAL_FIELDS = ["evidence", "symbol", "structural_hash"]

    @staticmethod
    def validate_signal(signal: dict) -> tuple[bool, list[str]]:
        """Validate signal structure."""
        errors = []

        for field in SignalValidator.REQUIRED_FIELDS:
            if field not in signal:
                errors.append(f"Missing required field: {field}")

        confidence = signal.get("confidence", "")
        if confidence not in ["high", "medium", "low"]:
            errors.append(f"Invalid confidence: {confidence}")

        return len(errors) == 0, errors


def run_friction_stress_test(brain, num_triggers: int = 100) -> dict:
    """
    Stress test friction triggers.

    Returns test results.
    """
    checker = VantageConsistencyChecker(brain)

    results = {
        "total_triggers": num_triggers,
        "valid_triggers": 0,
        "spam_detected": 0,
    }

    for i in range(num_triggers):
        is_valid, msg = checker.check_friction_trigger(
            f"test:signal:{i}",
            f"Test reason {i}",
        )

        if is_valid:
            results["valid_triggers"] += 1
        else:
            results["spam_detected"] += 1

    return results