import json
from typing import Any

VALID_DECISIONS = {"PASS", "WARN", "BLOCK"}


class OutputContractError(ValueError):
    pass


def normalize_output_contract(response_text: str) -> dict[str, Any]:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise OutputContractError("Invalid JSON") from exc

    if not isinstance(data, dict):
        raise OutputContractError("Top-level JSON must be an object")

    required = ("decision", "reason", "confidence")
    for key in required:
        if key not in data:
            raise OutputContractError(f"Missing required field: {key}")

    decision = data["decision"]
    if decision not in VALID_DECISIONS:
        raise OutputContractError("Invalid decision")

    reason = data["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise OutputContractError("Invalid reason")

    confidence = data["confidence"]
    if not isinstance(confidence, (int, float)):
        raise OutputContractError("Confidence must be numeric")
    confidence = float(confidence)
    if confidence < 0.0 or confidence > 1.0:
        raise OutputContractError("Confidence must be between 0.0 and 1.0")

    normalized: dict[str, Any] = {
        "decision": decision,
        "reason": reason.strip(),
        "confidence": confidence,
    }

    for optional_list in ("violations", "suggestions"):
        value = data.get(optional_list, [])
        if value is None:
            value = []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise OutputContractError(f"Invalid {optional_list}")
        normalized[optional_list] = value

    for optional_scalar in ("provider", "content"):
        value = data.get(optional_scalar)
        if value is not None:
            if not isinstance(value, str):
                raise OutputContractError(f"Invalid {optional_scalar}")
            normalized[optional_scalar] = value

    return normalized


def serialize_output_contract(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True)
