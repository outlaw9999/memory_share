from enum import StrEnum


class Action(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


def decide(signals: list) -> dict:
    """
    v1.2.5 Decision Engine (Thẩm phán L3).
    Deterministic judgment based on Signal confidence and MEC v1 Contract.
    Handles both Signal objects and serialized dictionaries.
    """
    if not signals:
        return {"action": Action.PASS, "exit_code": 0}

    # Helper to get confidence safely
    def get_conf(s):
        return s.get("confidence") if isinstance(s, dict) else getattr(s, "confidence", "low")

    # High confidence -> BLOCK (Niêm phong logic P0)
    has_high = any(get_conf(s) == "high" for s in signals)
    if has_high:
        return {
            "action": Action.BLOCK,
            "exit_code": 1,
            "reason": "High-confidence architectural signals detected."
        }

    # Medium/Low confidence -> WARN
    has_medium_low = any(get_conf(s) in ("medium", "low") for s in signals)
    if has_medium_low:
        return {
            "action": Action.WARN,
            "exit_code": 0,
            "reason": "Low-confidence smells detected. Review recommended."
        }

    return {"action": Action.PASS, "exit_code": 0}
