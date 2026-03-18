import time
import random
from typing import Dict, Any
from kit_agent.providers.base import BaseProvider

class MockChaosProvider(BaseProvider):
    def __init__(self, failure_rate=0.3):
        self.failure_rate = failure_rate

    def ask(self, prompt: str) -> Dict[str, Any]:
        time.sleep(0.5) # Simulate latency

        # 1. Simulate API failure (503/Timeout)
        if random.random() < self.failure_rate:
            return {"ok": False, "error": "Mocked 503 Capacity Exhausted", "text": "", "error_type": "CAPACITY"}

        # 2. Simulate Invariant Violation (To trigger Repair Loop)
        # We assume 'redis' is an invariant violation in this project
        if "REPAIR" in prompt.upper() or "FIX IT" in prompt.upper():
            # If in repair loop, return fixed output
            return {
                "ok": True, 
                "text": "import sqlite3\ndef get_cache(): return sqlite3.connect('brain.db')",
                "error": None,
                "error_type": None,
            }
        else:
            # First attempt: return violating output
            return {
                "ok": True,
                "text": "import redis\ncache = redis.Redis(host='localhost')",
                "error": None,
                "error_type": None,
            }
