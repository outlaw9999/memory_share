# .kit v1.2.5 - Titanium Contract Layer
# PURE SPECIFICATION: Normalized Mapping between Vantage (Physics) and SAMBrain (Cognition)

from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True)
class VantageMapping:
    """Rules for mapping a Vantage structural signal to an atomic fact."""

    SIGNAL_TO_TAG: ClassVar[dict[str, str]] = {
        "FUNCTION": "decision",
        "CLASS": "invariant",
        "MODULE": "invariant",
        "INTERFACE": "invariant",
        "STRUCT": "invariant",
        "SECURITY_SMELL": "friction",
        "COMPLEXITY_SMELL": "friction",
    }

    # Default Importance Weights based on structural hierarchy
    ROLE_WEIGHTS: ClassVar[dict[str, float]] = {
        "MODULE": 1.0,
        "CLASS": 0.9,
        "INTERFACE": 0.9,
        "FUNCTION": 0.7,
        "UNKNOWN": 0.5,
    }

    SYMBOL_ANKOR_TEMPLATE: ClassVar[str] = "Identity Anchor for symbol: {symbol}"

    @staticmethod
    def get_tag_for_type(signal_type: str) -> str:
        """Map Vantage internal type to KIT Fact Tag."""
        return VantageMapping.SIGNAL_TO_TAG.get(signal_type.upper(), "note")

    @staticmethod
    def get_importance(signal_type: str) -> float:
        """Determine base importance based on architectural scope."""
        return VantageMapping.ROLE_WEIGHTS.get(signal_type.upper(), 0.5)


def normalize_vantage_signal(raw_vantage_json: dict[str, Any]) -> dict[str, Any]:
    """
    Standardizes a raw Vantage signal into a KIT-compatible payload.
    Ensures zero-logic, pure-mapping consistency.
    """
    signal_type = raw_vantage_json.get("type", "UNKNOWN")
    symbol_id = raw_vantage_json.get("id", "anonymous")

    return {
        "uid": f"struct:{symbol_id}",
        "content": VantageMapping.SYMBOL_ANKOR_TEMPLATE.format(symbol=symbol_id),
        "tag": VantageMapping.get_tag_for_type(signal_type),
        "kind": "structural",
        "importance": VantageMapping.get_importance(signal_type),
        "symbol": symbol_id,
        "structural_hash": raw_vantage_json.get("normalized_hash"),
        "metadata": {
            "vantage_uuid": raw_vantage_json.get("uuid"),
            "ast_depth": raw_vantage_json.get("depth", 0),
            "engine": "vantage-verify-v1.2.5",
        },
    }
