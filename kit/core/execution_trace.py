"""Execution path observability for CLI/runtime boundaries."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kit.core.memory_topology import MemoryTopologyFactory

OBSERVABILITY_COMMANDS = {"stats", "trace"}


@dataclass(frozen=True, slots=True)
class ExecutionTraceEvent:
    timestamp: str
    command: str
    mode: str
    stage: str
    latency_ms: float
    success: bool
    fallback_reason: str | None = None
    metadata: dict[str, Any] | None = None


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def telemetry_path() -> Path:
    topo = MemoryTopologyFactory.global_only()
    return topo.resolve("global", "telemetry")


def log_execution_event(
    command: str,
    mode: str,
    stage: str,
    latency_ms: float,
    success: bool,
    fallback_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a single execution event to the global telemetry trace."""
    try:
        path = telemetry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        event = ExecutionTraceEvent(
            timestamp=datetime.now(UTC).isoformat(),
            command=command,
            mode=mode,
            stage=stage,
            latency_ms=round(max(0.0, latency_ms), 3),
            success=success,
            fallback_reason=fallback_reason,
            metadata=metadata or {},
        )
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")
    except Exception:
        pass


def read_execution_events(
    limit: int = 20,
    command: str | None = None,
    stage: str | None = None,
) -> list[dict[str, Any]]:
    """Read the most recent execution events with lightweight filtering."""
    path = telemetry_path()
    if not path.exists():
        return []

    matches: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if command and event.get("command") != command:
                continue
            if stage and event.get("stage") != stage:
                continue
            matches.append(event)

    if limit <= 0:
        return matches
    return matches[-limit:]


def summarize_execution_paths(limit: int = 200) -> dict[str, Any]:
    """Aggregate recent path telemetry into a compact cost summary."""
    events = read_execution_events(limit=limit)
    by_mode_stage: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    fallback_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    command_counts: Counter[str] = Counter()
    command_latency: dict[str, list[float]] = defaultdict(list)
    command_success: dict[str, list[bool]] = defaultdict(list)

    for event in events:
        mode = str(event.get("mode", "unknown"))
        stage = str(event.get("stage", "unknown"))
        command = str(event.get("command", "unknown"))
        latency = float(event.get("latency_ms", 0.0) or 0.0)
        success = bool(event.get("success", False))

        by_mode_stage[mode][stage].append(latency)
        stage_counts[stage] += 1
        command_counts[command] += 1
        command_latency[command].append(latency)
        command_success[command].append(success)

        fallback_reason = event.get("fallback_reason")
        if fallback_reason:
            fallback_counts[str(fallback_reason)] += 1

    summary: dict[str, dict[str, Any]] = {}
    for mode, stages in by_mode_stage.items():
        summary[mode] = {}
        for stage, latencies in stages.items():
            successes = [
                bool(event.get("success", False))
                for event in events
                if event.get("mode") == mode and event.get("stage") == stage
            ]
            summary[mode][stage] = {
                "count": len(latencies),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
                "p95_latency_ms": round(_percentile(latencies, 0.95), 3) if latencies else 0.0,
                "success_rate": round(sum(1 for ok in successes if ok) / len(successes), 3) if successes else 0.0,
            }

    command_summary = []
    for command, count in command_counts.most_common(10):
        latencies = command_latency[command]
        successes = command_success[command]
        command_summary.append(
            {
                "command": command,
                "count": count,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
                "success_rate": round(sum(1 for ok in successes if ok) / len(successes), 3) if successes else 0.0,
            }
        )

    return {
        "telemetry_path": str(path_or_missing()),
        "sample_size": len(events),
        "stages": dict(stage_counts),
        "path_summary": summary,
        "fallback_reasons": dict(fallback_counts),
        "top_commands": command_summary,
    }


def summarize_hot_paths(limit: int = 200) -> dict[str, Any]:
    """Rank commands by executor-heavy cost using recent telemetry."""
    events = read_execution_events(limit=limit)
    by_command_stage: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    command_success: dict[str, list[bool]] = defaultdict(list)

    for event in events:
        command = str(event.get("command", "unknown"))
        if command in OBSERVABILITY_COMMANDS:
            continue
        stage = str(event.get("stage", "unknown"))
        latency = float(event.get("latency_ms", 0.0) or 0.0)
        success = bool(event.get("success", False))

        by_command_stage[command][stage].append(latency)
        command_success[command].append(success)

    hotpaths: list[dict[str, Any]] = []
    for command, stages in by_command_stage.items():
        dispatch_latencies = stages.get("dispatch", [])
        parser_latencies = stages.get("parser", [])
        executor_latencies = stages.get("executor", [])
        if not executor_latencies:
            continue
        total_events = sum(len(values) for values in stages.values())
        success_rate = (
            round(sum(1 for ok in command_success[command] if ok) / len(command_success[command]), 3)
            if command_success[command]
            else 0.0
        )

        avg_dispatch = round(sum(dispatch_latencies) / len(dispatch_latencies), 3) if dispatch_latencies else 0.0
        avg_parser = round(sum(parser_latencies) / len(parser_latencies), 3) if parser_latencies else 0.0
        avg_executor = round(sum(executor_latencies) / len(executor_latencies), 3) if executor_latencies else 0.0
        reasoning_depth = round(max(0.0, avg_executor - avg_dispatch), 3)
        variance = round(_percentile(executor_latencies, 0.95) - avg_executor, 3) if executor_latencies else 0.0

        if avg_executor >= 50 or reasoning_depth >= 40:
            band = "high"
        elif avg_executor >= 10 or reasoning_depth >= 8:
            band = "medium"
        else:
            band = "low"

        hotpaths.append(
            {
                "command": command,
                "event_count": total_events,
                "executor_count": len(executor_latencies),
                "avg_dispatch_ms": avg_dispatch,
                "avg_parser_ms": avg_parser,
                "avg_executor_ms": avg_executor,
                "reasoning_depth_ms": reasoning_depth,
                "executor_variance_ms": variance,
                "success_rate": success_rate,
                "cost_band": band,
            }
        )

    hotpaths.sort(
        key=lambda item: (
            -item["reasoning_depth_ms"],
            -item["avg_executor_ms"],
            -item["event_count"],
            item["command"],
        )
    )

    return {
        "telemetry_path": str(path_or_missing()),
        "sample_size": len(events),
        "hotpaths": hotpaths,
    }


def path_or_missing() -> Path:
    try:
        return telemetry_path()
    except Exception:
        home = Path(os.environ.get("KIT_GLOBAL_HOME", Path.home() / ".kit"))
        return home / "routing_telemetry.jsonl"
