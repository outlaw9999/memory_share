# kit/cih/vantage_hook_adapter.py

from collections.abc import Callable
from typing import Any, Dict, Optional

from kit.cih.runtime_injector import CIHRuntimeInjector


class VantageExecutionHookAdapter:
    """
    ZERO-TOUCH instrumentation layer.

    PURPOSE:
    - Attach to Vantage execution without modifying core logic
    - Intercept only metadata, not execution
    """

    def __init__(self, injector: CIHRuntimeInjector):
        self.injector = injector

    # -----------------------------
    # PRE-HOOK (optional)
    # -----------------------------
    def pre(self, node: dict[str, Any], context: dict[str, Any]) -> None:
        """
        Called BEFORE execution (lightweight capture only).
        """
        event = self._build_event(node, context, phase="pre")
        self.injector.post(event)

    # -----------------------------
    # POST-HOOK (primary signal)
    # -----------------------------
    def post(
        self,
        node: dict[str, Any],
        context: dict[str, Any],
        result: Any | None = None,
        error: Exception | None = None,
        execution_time_ms: float = 0.0,
    ) -> None:
        """
        Called AFTER execution completes.
        """

        event = self._build_event(
            node,
            context,
            phase="post",
            result=result,
            error=error,
            execution_time_ms=execution_time_ms,
        )

        self.injector.post(event)

    # -----------------------------
    # EVENT BUILDER (VantageCIHEvent v1.0)
    # -----------------------------
    def _build_event(
        self,
        node: dict[str, Any],
        context: dict[str, Any],
        phase: str,
        result: Any = None,
        error: Exception | None = None,
        execution_time_ms: float = 0.0,
    ) -> dict[str, Any]:

        fan_in = len(context.get("inputs", []))
        fan_out = len(context.get("outputs", []))

        return {
            "node": node,
            "execution": {
                "fanout": fan_out,
                "retry_count": context.get("retry_count", 0),
                "depth": context.get("cycle_count", 0),
                "duration_ms": execution_time_ms
            },
            "signal": {
                "error_rate": 1.0 if error is not None else 0.0
            },
            "graph": {
                "dependency_count": fan_in,
                "hot_path": context.get("hot_path", False),
                "centrality": context.get("centrality", 0.0)
            },
            "phase": phase,
            "result_type": type(result).__name__ if result is not None else None,
        }
