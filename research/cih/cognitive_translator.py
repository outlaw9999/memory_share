# kit/cih/cognitive_translator.py

from __future__ import annotations
from typing import Dict, Any
from kit.core.memory_router import MemoryWriteRequest, WriteSource


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


class CIHCognitiveTranslator:
    """
    Pure deterministic mapping:
    Physics Signal -> MemoryWriteRequest
    """

    __slots__ = ()

    def translate(self, signal: Dict[str, Any]) -> MemoryWriteRequest:

        stability = signal["stability"]
        volatility = signal["volatility"]
        pressure = signal["pressure"]

        # --- confidence model (deterministic fusion) ---
        confidence = _clamp(
            (stability * 0.65) +
            ((1.0 - min(volatility, 1.0)) * 0.25) +
            (_clamp(signal["centrality"]) * 0.10)
        )

        # --- semantic tagging (rule-based only) ---
        if signal["hot_path"]:
            tag = "hot_execution"
        elif pressure > 10:
            tag = "high_pressure"
        elif volatility > 50:
            tag = "unstable_execution"
        else:
            tag = "normal_execution"

        return MemoryWriteRequest(
            source=WriteSource.KIT_SCAN,
            key=f"cih:{signal['node_id']}",
            content=signal,
            confidence=confidence,
            metadata={
                "cih": True,
                "pressure": pressure,
                "volatility": volatility,
                "stability": stability,
                "tag": tag
            },
            source_metadata={
                "layer": "cih",
                "version": "1.0",
                "raw_event": signal.get("raw")
            },
            reason="CIH deterministic signal translation"
        )
