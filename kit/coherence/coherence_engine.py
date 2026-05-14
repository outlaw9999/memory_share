from typing import Any, Dict, List

from kit.core.coherence_schema import CoherentMemory, ConflictType
from kit.core.memory_policy import MemoryPolicy


class MemoryCoherenceEngine:
    """
    Simplified MCE (1.2.5COLLAPSE).
    Delegates all logic to the unified MemoryPolicy.
    """

    def resolve(self, key: str, local=None, global_=None, frozen=None):
        candidates = [m for m in [local, global_, frozen] if m is not None]
        winner = MemoryPolicy.resolve(candidates)

        if not winner:
            return None

        # Maintain contract with CoherentMemory wrapper
        import time

        now = time.time()
        return CoherentMemory(
            key=key,
            content=winner.content,
            confidence=MemoryPolicy.calculate_score(winner, now),
            source_tier=getattr(winner, "brain_source", "local"),
            conflict_state=ConflictType.NONE,  # Simplified
        )

    def merge(self, memories: list[Any]) -> list[Any]:
        """
        Unified Merge Gate.
        """
        if not memories:
            return []

        # Grouping by symbol remains for bulk processing
        buckets: dict[str, list[Any]] = {}
        for m in memories:
            key = getattr(m, "symbol", "generic")
            buckets.setdefault(key, []).append(m)

        resolved = []
        for key, group in buckets.items():
            winner = MemoryPolicy.resolve(group)
            if winner:
                resolved.append(winner)

        return resolved
