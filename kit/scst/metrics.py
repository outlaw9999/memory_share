# kit/scst/metrics.py

from typing import Dict, Any

class SCSTMetrics:
    """
    SCST Metrics System:
    Calculates the final Stability Score (SCST_SCORE).
    """
    @staticmethod
    def evaluate_stability(metrics: Dict[str, Any]) -> float:
        total = metrics.get("total_events", 1)
        
        determinism = 1.0 - (metrics.get("routing_errors", 0) / total)
        authority = 1.0 - (metrics.get("authority_violations", 0) / total)
        stability = 1.0 - (metrics.get("coherence_failures", 0) / total)
        isolation = 1.0 - (metrics.get("cih_drops", 0) / total)
        
        # SCST_SCORE Formula:
        # 0.4 * determinism + 0.3 * authority + 0.2 * stability + 0.1 * isolation
        score = (
            0.4 * determinism +
            0.3 * authority +
            0.2 * stability +
            0.1 * isolation
        )
        return round(score, 4)

    @staticmethod
    def classify_failure(metrics: Dict[str, Any]) -> str:
        if metrics.get("authority_violations", 0) > 0:
            return "Mode A: Authority Collapse"
        if metrics.get("coherence_failures", 0) > 0:
            return "Mode B: Temporal Bleed / Coherence Failure"
        if metrics.get("cih_drops", 0) > (metrics.get("total_events", 0) * 0.5):
            return "Mode C: CIH Leakage / Buffer Exhaustion"
        return "System Healthy"
