"""
identity_guard.py — KIT v1.2.5: The Identity Firewall.
Enforces structural hash consistency and agent authority boundaries.
"""

from typing import Any

TRUSTED_AUTHORITIES = {"governor", "senior", "system"}


def validate_authority(agent_id: str | None, proposed_baked: bool) -> bool:
    """
    Check if the agent is authorized to graduate an observation.
    Only trusted authorities can set is_baked=True.
    """
    if not proposed_baked:
        return True  # Anyone can submit raw perception

    return agent_id in TRUSTED_AUTHORITIES


def check_identity_hijack(symbol: str, proposed_hash: str | None, anchor_hash: str | None) -> dict[str, Any]:
    """
    Check if a new perception is attempting to hijack a known symbol's identity.
    Returns forensic markers for the StateVector if a hijack is detected.
    """
    # If no anchor exists, it's a new identity or unverified state
    if anchor_hash is None or proposed_hash is None:
        return {}

    # If hashes mismatch, it's a structural drift explosion (Identity Hijack)
    if proposed_hash != anchor_hash:
        return {"state": "BLOCK", "reason": "IDENTITY_MISMATCH", "severity": "HIGH", "requires_review": True}

    return {}
