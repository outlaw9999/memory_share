# kit/memory/projection.py
# v1.2.5 — MemoryProjection: pure projection engine for the closed-loop architecture.
#
# Memory is NOT written. Memory is PROJECTED from validated execution traces.
# This is the ONLY component allowed to persist state.
#
# INVARIANTS:
#   - Receives only already-approved execution traces (verified by kit-vantage)
#   - No decision logic — validation happened upstream
#   - No filtering — filtering happened upstream
#   - No intelligence — pure mechanical projection
#
# AUTHORITY:
#   State Sink: Single write path. Projects approved traces to correct tier.
#   Forbidden: Self-authoring, speculative writes, truth evaluation.

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from kit.intent.schema import CanonicalIntent

logger = logging.getLogger("kit.memory.projection")


@dataclass
class ProjectionRequest:
    """
    The ONLY valid input to MemoryProjection.
    Pre-validated by kit-vantage (epistemic gate) and PolicyGuard (safety gate).
    No decision needed — only projection.
    """
    intent: CanonicalIntent
    content: str
    tag: str = "observation"
    source: str = "runtime"
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectionReceipt:
    """Receipt of a successful projection. No decisions — only confirmation."""
    target_tier: str
    observation_id: int
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


_MEMORY_ROUTER: Any | None = None


def _get_router():
    """Lazy import to avoid circular dependency with kit.core."""
    global _MEMORY_ROUTER
    if _MEMORY_ROUTER is None:
        from kit.core.memory_router import MemoryRouter, MemoryWriteRequest, WriteSource
        from kit.core.memory_topology import MemoryTopologyFactory
        topology = MemoryTopologyFactory.detect()
        _MEMORY_ROUTER = MemoryRouter(topology=topology)
    return _MEMORY_ROUTER


@dataclass
class MemoryProjection:
    """Pure projection engine. No decisions. No validation. Only projection."""

    @staticmethod
    def project(request: ProjectionRequest) -> ProjectionReceipt:
        """
        Project an approved execution trace to memory.

        Called AFTER kit-vantage approval and PolicyGuard clearance.
        Never validates. Never decides. Only projects.
        """
        router = _get_router()

        # Determine target tier mechanically based on content characteristics
        target_tier = MemoryProjection._determine_tier(request.content, request.tag)

        # Build the write request — no validation, no decision
        from kit.core.memory_router import MemoryTier, MemoryWriteRequest, WriteSource

        write_request = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key=f"{request.intent}:{request.trace_id}",
            content=request.content,
            confidence=1.0,  # Already approved — full confidence
            metadata={
                "source": request.source,
                "trace_id": request.trace_id,
                "tag": request.tag,
                **request.metadata,
            },
            tag=request.tag,
            target_tier=target_tier,
        )

        receipt = router.route_write(write_request)

        return ProjectionReceipt(
            target_tier=receipt.assigned_tier.value if receipt.assigned_tier else "unknown",
            observation_id=receipt.observation_id or 0,
        )

    @staticmethod
    def _determine_tier(content: str, tag: str) -> Any | None:
        """Mechanical tier routing based on data characteristics, not decisions."""
        from kit.core.memory_router import MemoryTier

        # Long-term important observations go to GLOBAL
        if tag in ("decision", "invariant", "rule", "commit"):
            return MemoryTier.GLOBAL
        # Ephemeral observations stay LOCAL
        return MemoryTier.LOCAL
