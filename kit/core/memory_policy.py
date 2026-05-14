# kit/core/memory_policy.py

import math
import time
from datetime import datetime
from typing import Any, List, Optional


class MemoryPolicy:
    """
    The Single Authority for Memory Truth (v1.2.5-TITANIUM-FROZEN).
    Consolidates Arbitration, Scoring, and Temporal Decay into one deterministic path.
    """

    POLICY_VERSION = "1.2.5-TITANIUM-FROZEN"

    TIER_WEIGHTS = {"frozen": 1.0, "law": 1.0, "global": 0.7, "local": 0.5}

    # --- SQL Authority Constants (v1.2.5-TITANIUM) ---
    # These ensure that even SQL-level ranking follows the unified kernel logic.

    SQL_RANKING_FORMULA = """
        importance * 
        ((access_count + 2) / (access_count + 6.0)) *
        CASE layer
            WHEN 'working'  THEN 3.0
            WHEN 'episodic' THEN 2.0
            WHEN 'semantic' THEN 1.5
            ELSE 1.0
        END
    """

    SQL_MATERIALIZE_SCORE = f"""
        UPDATE observations
        SET materialized_score = {SQL_RANKING_FORMULA} *
        CASE 
            WHEN (julianday('now') - julianday(created_at)) < 1  THEN 1.0
            WHEN (julianday('now') - julianday(created_at)) < 7  THEN 0.9
            WHEN (julianday('now') - julianday(created_at)) < 30 THEN 0.7
            ELSE 0.4
        END
        WHERE is_active = 1 AND superseded_at IS NULL
    """

    SQL_RECALL_BASE = """
        SELECT n.uid, o.id, o.importance, o.created_at, o.content 
        FROM observations o
        JOIN nodes n ON o.node_id = n.id
        WHERE o.is_active = 1
    """

    TAG_PRIORITY = {
        "invariant": 3,
        "decision": 2,
        "preference": 1,
        "skill": 1,
        "pattern": 1,
        "note": 0,
        "friction": 0,
        "legacy": 0,
        "hypothesis": 0,
    }

    @staticmethod
    def calculate_confidence(importance: float) -> float:
        """
        [FROZEN v1.2.5] Authority Rule for Importance-to-Confidence mapping.
        """
        return min(0.94, (importance / 10.0) + 0.5)

    @staticmethod
    def calculate_score(memory: Any, now: float | None = None) -> float:
        """
        [FROZEN v1.2.5] Deterministic Unified Scoring Function.
        score = confidence * e^(-decay_rate * age) * tier_weight
        """
        now = now if now is not None else time.time()

        # 1. Base confidence fallback logic: confidence -> raw importance -> default
        # We explicitly avoid using 'memory.score' here if possible, as that might be
        # a weighted score (materialized_score).
        confidence = getattr(memory, "confidence", None)
        if confidence is None:
            importance = getattr(memory, "importance", 1.0)
            # Standard kit formula: importance scaled to 0.5-0.94 range
            confidence = min(0.94, (importance / 10.0) + 0.5)

        # 2. Stable timestamp handling
        ts_val = getattr(memory, "created_at", now)

        if ts_val is None:
            ts = now
        elif isinstance(ts_val, str):
            try:
                # Handle ISO format
                ts_str = ts_val.replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str).timestamp()
            except Exception:
                ts = now
        else:
            try:
                ts = float(ts_val)
            except TypeError, ValueError:
                ts = now

        # 3. Deterministic age with safety clamp (1s resolution)
        age_days = max(0.0, (now - ts) / 86400.0)
        decay = math.exp(-0.01 * age_days)

        # 4. Tier Authority
        tier = getattr(memory, "brain_source", "local")
        weight = MemoryPolicy.TIER_WEIGHTS.get(tier, 0.5)

        return confidence * decay * weight

    @staticmethod
    def canonical_sort_key(memory: Any, score: float, now: float, boost: float = 0.0) -> tuple:
        """
        [FROZEN v1.2.5] The Five-Layer Deterministic Tie-Break Contract.
        1. score + boost (desc)
        2. tier_weight (desc)
        3. tag_priority (desc)
        4. created_at_bucket (1s coarse quantization) (desc)
        5. runtime_hash (high-entropy content lock) (desc)
        6. mem_id (final machine-local total order anchor) (desc)
        """
        tier = getattr(memory, "brain_source", "local")
        tier_weight = MemoryPolicy.TIER_WEIGHTS.get(tier, 0.5)
        tag = getattr(memory, "tag", "decision")
        tag_prio = MemoryPolicy.TAG_PRIORITY.get(tag, 0)

        # Synchronized timestamp extraction
        ts_val = getattr(memory, "created_at", now)
        if isinstance(ts_val, str):
            try:
                ts_str = ts_val.replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str).timestamp()
            except Exception:
                ts = now
        else:
            try:
                ts = float(ts_val) if ts_val else now
            except TypeError, ValueError:
                ts = now

        runtime_hash = getattr(memory, "_runtime_hash", 0) or 0
        mem_id = getattr(memory, "id", 0) or 0

        return (
            tag_prio,  # 1. Authority Plane (The Law)
            boost,  # 2. Contextual Plane (The Scope)
            tier_weight,  # 3. Source Plane (The Provenance)
            score,  # 4. Signal Plane (The Importance/Decay)
            int(ts),  # 5. Stability Plane
            runtime_hash,  # 6. Content Lock
            mem_id,  # 7. Final Anchor
        )

    @staticmethod
    def resolve(candidates: list[Any], now: float | None = None, context: dict | None = None) -> Any | None:
        """
        [FROZEN v1.2.5] Deterministic Arbitration via Canonical Contract.
        Entry point for single-winner resolution.
        """
        results = MemoryPolicy.arbitrate(candidates, context=context, limit=1, now=now)
        return results[0] if results else None

    @staticmethod
    def get_boosted_score(m: Any, context: dict, now: float) -> float:
        """Calculate the final arbitrated score for a memory in context."""
        score = MemoryPolicy.calculate_score(m, now)
        boost = 0.0

        agent_id = context.get("agent_id")
        scope = context.get("scope")
        symbol = context.get("symbol")
        m_scope = getattr(m, "scope", "") or ""

        if scope and m_scope == scope:
            boost += 0.5
        elif scope and m_scope and scope.startswith(m_scope):
            boost += 0.2
        elif m_scope in ("", "global"):
            boost += 0.1

        if symbol and getattr(m, "symbol", None) == symbol:
            boost += 0.3
        if agent_id and getattr(m, "namespace", None) == agent_id:
            boost += 0.2

        if getattr(m, "tag", "") == "invariant":
            boost += 100.0

        return score + boost

    @staticmethod
    def arbitrate(
        candidates: list[Any],
        context: dict | None = None,
        limit: int = 15,
        now: float | None = None,
        deduplicate: bool = True,
    ) -> list[Any]:
        """
        [FROZEN v1.2.5] Deterministic Ranking & Arbitration Kernel.
        The Single Decision Surface for all memory recall.
        """
        if not candidates:
            return []

        now = now if now is not None else time.time()
        context = context or {}

        # Extract context boosts
        context.get("agent_id")
        context.get("scope")
        context.get("symbol")

        scored = []
        for m in candidates:
            # v1.2.5-TITANIUM: Collapse Arbitration Authority to get_boosted_score
            final_score = MemoryPolicy.get_boosted_score(m, context, now)

            # Canonical Sort Key (Determinism Plane)
            # Note: canonical_sort_key already takes (score + boost) as its first argument
            key = MemoryPolicy.canonical_sort_key(m, 0.0, now, boost=final_score)
            scored.append((key, m))

        # 4. Deterministic Sort (Descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        # DEBUG: Print keys for hierarchy verification
        for k, m in scored:
            import logging

            logging.getLogger("kit.memory_policy").debug(
                f"ARBITRATE: key={k}, tag={getattr(m, 'tag', 'N/A')}, id={getattr(m, 'id', 0)}"
            )

        # 5. Deduplication (Logic Collapse: Prioritize highest rank for same UID)
        if not deduplicate:
            return [m for _, m in scored][:limit]

        seen_uids = set()
        final = []
        for _, m in scored:
            uid = getattr(m, "node_uid", None) or getattr(m, "id", None)
            if uid not in seen_uids:
                final.append(m)
                seen_uids.add(uid)
                if len(final) >= limit:
                    break

        return final
