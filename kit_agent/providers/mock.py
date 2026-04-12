import json
import random
import time
from typing import Any

from kit_agent.providers.base import BaseProvider


class MockChaosProvider(BaseProvider):
    def __init__(self, failure_rate=0.3):
        self.failure_rate = failure_rate

    def ask(self, prompt: str) -> dict[str, Any]:
        time.sleep(0.5)  # Simulate latency

        # 1. Simulate API failure (503/Timeout)
        if random.random() < self.failure_rate:
            return {"ok": False, "error": "Mocked 503 Capacity Exhausted", "text": "", "error_type": "CAPACITY"}

        # 2. Simulate Invariant Violation (To trigger Repair Loop)
        # We assume 'redis' is an invariant violation in this project
        if "REPAIR" in prompt.upper() or "FIX IT" in prompt.upper():
            # If in repair loop, return fixed output
            return {
                "ok": True,
                "text": json.dumps(
                    {
                        "decision": "PASS",
                        "reason": "Repaired output now aligns with the SQLite constraint.",
                        "confidence": 0.8,
                    }
                ),
                "error": None,
                "error_type": None,
            }
        else:
            # First attempt: return violating output
            return {
                "ok": True,
                "text": json.dumps(
                    {
                        "decision": "WARN",
                        "reason": "Initial mock response is intentionally unstable to exercise repair and fallback behavior.",
                        "confidence": 0.3,
                    }
                ),
                "error": None,
                "error_type": None,
            }
