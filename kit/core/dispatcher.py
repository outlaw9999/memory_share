"""
Kit Execution Dispatcher
Entry point: routes commands based on execution mode without AGENTS.md overhead.
"""

import logging
import sys
import time
from typing import Any, Optional

from kit.core.command_routes import COMMANDS, DEFAULT_MODE
from kit.core.execution_trace import log_execution_event

logger = logging.getLogger("kit.dispatcher")


def direct_execute(command: str, args: Any) -> int:
    """Direct path: no reasoning, call executor immediately."""
    route = COMMANDS.get(command)
    if not route:
        logger.error("Unknown direct command: %s", command)
        log_execution_event(
            command=command,
            mode="direct",
            stage="executor",
            latency_ms=0.0,
            success=False,
            fallback_reason="unknown_command",
        )
        return 1

    executor = route["executor"]
    start = time.perf_counter()

    try:
        if executor == "vantage":
            from kit.core.vantage_dispatch import run_vantage

            result = run_vantage(command, args)
        elif executor == "fs":
            from kit.core.fs_dispatch import run_fs

            result = run_fs(command, args)
        elif executor == "graph":
            from kit.graph.api import quick_blast

            result = 0
        else:
            logger.error(f"Unknown executor: {executor}")
            result = 1

        log_execution_event(
            command=command,
            mode="direct",
            stage="executor",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=result == 0,
            fallback_reason=None if executor in {"vantage", "fs", "graph"} else "unknown_executor",
            metadata={"executor": executor},
        )
        return result
    except Exception as exc:
        log_execution_event(
            command=command,
            mode="direct",
            stage="executor",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            metadata={"executor": executor, "error": str(exc)},
        )
        raise


def light_route(command: str, args: Any) -> int:
    """Routed path: graph lookup + light routing."""
    executor = COMMANDS.get(command, {}).get("executor", "memory")
    start = time.perf_counter()

    try:
        if executor == "graph":
            from kit.graph.validation import GraphValidationHarness

            logger.debug(f"Graph routing for {command}")
            result = 0
        elif executor == "memory":
            from kit.core.memory_router import route_memory

            result = route_memory(command, args)
        else:
            result = full_reasoning(command, args)

        log_execution_event(
            command=command,
            mode="routed",
            stage="executor",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=result == 0,
            metadata={"executor": executor},
        )
        return result
    except Exception as exc:
        log_execution_event(
            command=command,
            mode="routed",
            stage="executor",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            metadata={"executor": executor, "error": str(exc)},
        )
        raise


def full_reasoning(command: str, args: Any) -> int:
    """Diagnostic path: AGENTS.md reasoning (ONLY when explicitly needed)."""
    logger.info(f"Diagnostic mode for {command}")
    # AGENTS.md loaded here ONLY
    start = time.perf_counter()
    try:
        from kit.core.kit_cognitive_core import CognitiveCore

        core = CognitiveCore()
        result = core.execute_diagnostic(command, args)
        log_execution_event(
            command=command,
            mode="diagnostic",
            stage="executor",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=result == 0,
        )
        return result
    except Exception as exc:
        log_execution_event(
            command=command,
            mode="diagnostic",
            stage="executor",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            metadata={"error": str(exc)},
        )
        raise


def dispatch(command: str, args: Any) -> int:
    """
    Main dispatcher - O(1) routing decision.
    NO AGENTS.md loaded unless mode == diagnostic.
    """
    start = time.perf_counter()
    route = COMMANDS.get(command)
    if not route:
        logger.error("Unknown routed command: %s", command)
        log_execution_event(
            command=command,
            mode="standard",
            stage="dispatch",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            fallback_reason="unknown_command",
        )
        return 1

    mode = route.get("mode", DEFAULT_MODE)

    logger.debug(f"Dispatch: {command} -> {mode}")
    log_execution_event(
        command=command,
        mode=mode,
        stage="dispatch",
        latency_ms=(time.perf_counter() - start) * 1000,
        success=True,
        metadata={"executor": route.get("executor")},
    )

    if mode == "direct":
        return direct_execute(command, args)
    elif mode == "routed":
        return light_route(command, args)
    else:
        return full_reasoning(command, args)


def classify(command: str) -> str:
    """Return execution mode for a command without dispatching."""
    route = COMMANDS.get(command)
    return route.get("mode", DEFAULT_MODE) if route else DEFAULT_MODE
