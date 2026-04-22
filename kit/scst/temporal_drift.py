# kit/scst/temporal_drift.py

import time
from typing import Dict, Any, List

class TemporalDriftSimulator:
    """
    SCST Temporal Drift Simulator:
    Challenges MCE v2's temporal stability and exponential decay logic.
    """
    def generate_scenario(self, base_content: Any) -> List[Dict[str, Any]]:
        now = time.time()
        return [
            {
                "id": "DRIFT-T0",
                "content": base_content,
                "timestamp": now - 86400 * 100,  # 100 days old
                "confidence": 0.9,
                "tier": "global"
            },
            {
                "id": "DRIFT-T1",
                "content": f"Modified: {base_content}",
                "timestamp": now - 86400 * 5,    # 5 days old
                "confidence": 0.5,
                "tier": "local"
            },
            {
                "id": "DRIFT-T2",
                "content": "Contradictory Fact",
                "timestamp": now - 3600,        # 1 hour old
                "confidence": 0.4,
                "tier": "local"
            }
        ]
