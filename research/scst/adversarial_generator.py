# kit/scst/adversarial_generator.py

from typing import Any, Dict, List


class AdversarialQueryGenerator:
    """
    SCST Adversarial Query Generator:
    Attempts to force routing errors via semantic ambiguity and tier confusion baits.
    """
    def generate(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "ADV-001",
                "query": "auth middleware optimization pattern",
                "noise": "local experimental override bait",
                "expected_tier": "global",
                "intent": "tier_confusion"
            },
            {
                "id": "ADV-002",
                "query": "json parsing internal micro-optimization",
                "noise": "frozen contradiction bait",
                "expected_tier": "frozen",
                "intent": "authority_bypass"
            },
            {
                "id": "ADV-003",
                "query": "temporary variable cleanup",
                "noise": "global pattern noise",
                "expected_tier": "local",
                "intent": "scope_drift"
            }
        ]
