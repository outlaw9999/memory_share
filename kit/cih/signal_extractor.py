# kit/cih/signal_extractor.py

from __future__ import annotations
from typing import Any, Dict


class CIHSignalExtractor:
    """
    Pure functional extractor:
    Vantage Event -> Raw Physics Signal
    No side effects. No dependencies.
    """

    __slots__ = ()

    def extract(self, event: Dict[str, Any]) -> Dict[str, Any]:
        node = event["node"]
        exec_ = event["execution"]
        sig = event["signal"]
        graph = event["graph"]

        fan_in = max(1, graph.get("dependency_count", 0))
        fan_out = max(1, exec_.get("fanout", 0))

        # --- Stability (LOCKED FORMULA) ---
        error = sig.get("error_rate", 0.0)
        retry = exec_.get("retry_count", 0)
        cycle = exec_.get("depth", 0)

        stability = 1.0 / (1.0 + cycle + int(error > 0) + retry)

        # --- Pressure (LOCKED FORMULA) ---
        pressure = fan_in * fan_out

        # --- Volatility (LOCKED FORMULA) ---
        exec_time = exec_.get("duration_ms", 0.0)
        volatility = exec_time / (fan_in + 1.0)

        return {
            "node_id": node["id"],
            "stability": stability,
            "pressure": float(pressure),
            "volatility": float(volatility),
            "hot_path": graph.get("hot_path", False),
            "centrality": graph.get("centrality", 0.0),
            "raw": event
        }
