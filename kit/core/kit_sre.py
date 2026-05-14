"""Symbol Reconciliation Engine (SRE v1.0).

Manages the semantic metabolism of symbols:
- Detects drift between locked symbols and heuristic reality.
- Generates explainable evolution proposals.
- Maintains an append-only evolution graph.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.sre")

# --- SRE Constants & Thresholds ---
DRIFT_THRESHOLD_OBSOLETE = 0.50
DRIFT_THRESHOLD_TRANSITION = 0.75
SAMPLING_RATE = 0.20  # 20% write-time sampling

DOMAIN_SENSITIVITY = {
    "auth": 1.2,
    "db": 1.1,
    "arch": 1.3,
    "fin": 1.5,
    "agent": 1.0,
    "test": 0.5,
}


@dataclass(frozen=True)
class DriftMetrics:
    symbol: str
    hard_signals: dict[str, float]
    soft_signals: dict[str, float]
    context_signals: dict[str, float]
    final_score: float

    def to_json(self) -> str:
        return json.dumps(
            {
                "hard": self.hard_signals,
                "soft": self.soft_signals,
                "context": self.context_signals,
                "final": round(self.final_score, 4),
            }
        )


class SREEngine:
    """Core logic for symbol metabolism and reconciliation."""

    def __init__(self, brain: SAMBrain):
        self.brain = brain

    def run_drift_monitor(self, force: bool = False):
        """Scan locked symbols and evaluate drift levels."""
        try:
            with self.brain.get_connection(readonly=True) as conn:
                locked_symbols = conn.execute("SELECT symbol FROM symbol_nodes WHERE locked = 1").fetchall()

            for (symbol,) in locked_symbols:
                metrics = self.evaluate_symbol_drift(symbol)
                if metrics.final_score >= DRIFT_THRESHOLD_OBSOLETE:
                    self._record_drift_event(metrics)
                    if metrics.final_score >= DRIFT_THRESHOLD_TRANSITION:
                        self._generate_evolution_proposal(metrics)

        except Exception as e:
            logger.error(f"SRE: Drift monitor failed: {e}")

    def evaluate_symbol_drift(self, symbol: str) -> DriftMetrics:
        """
        Explained Scoring Model (Stage 5.5):
        - Layer A: Hard Signals (Deterministic)
        - Layer B: Soft Signals (Tunable)
        - Layer C: Context Signals (Adaptive)
        """
        hard = self._calculate_hard_signals(symbol)
        soft = self._calculate_soft_signals(symbol)
        context = self._calculate_context_signals(symbol)

        # Weighted decomposition (Explainable Sum)
        # We don't collapse into a single weight too early,
        # but for the 'final_score' we use a balanced mix.

        # Hard signals weigh more for stability
        h_score = hard["lock_violation_rate"] * 0.6 + hard["ambiguity_density"] * 0.4
        # Soft signals contribute to gradual pressure
        s_score = soft["temporal_decay"] * 0.3 + soft["repair_pressure"] * 0.7

        raw_score = (h_score * 0.6) + (s_score * 0.4)

        # Apply context sensitivity
        final_score = raw_score * context.get("sensitivity_multiplier", 1.0)

        return DriftMetrics(
            symbol=symbol,
            hard_signals=hard,
            soft_signals=soft,
            context_signals=context,
            final_score=min(1.0, final_score),
        )

    def _calculate_hard_signals(self, symbol: str) -> dict[str, float]:
        """Layer A: Factual violations and measurable ambiguity."""
        with self.brain.get_connection(readonly=True) as conn:
            # 1. Lock Violation Rate:
            # How many times did heuristic disagree with this locked symbol?
            ambiguity_data = conn.execute(
                """
                SELECT COUNT(*), AVG(confidence) 
                FROM symbol_ambiguities 
                WHERE chosen_symbol != ?
                  AND observation_id IN (SELECT id FROM observations WHERE symbol = ?)
            """,
                (symbol, symbol),
            ).fetchone()

            total_ambiguities = ambiguity_data[0] or 0
            avg_confidence = ambiguity_data[1] or 0.0

            # 2. Heuristic pressure: Observations where heuristic would have picked a different symbol
            # (already captured by total_ambiguities in the updated query above)

            return {
                "lock_violation_rate": min(1.0, total_ambiguities / 5.0),  # Normalize at 5 mismatches
                "ambiguity_density": min(1.0, total_ambiguities / 3.0),
                "heuristic_confidence_delta": round(1.0 - avg_confidence, 4),
            }

    def _calculate_soft_signals(self, symbol: str) -> dict[str, float]:
        """Layer B: Temporal decay and gradual semantic pressure."""
        with self.brain.get_connection(readonly=True) as conn:
            node_data = conn.execute("SELECT created_at FROM symbol_nodes WHERE symbol = ?", (symbol,)).fetchone()

            if not node_data:
                return {"temporal_decay": 0.0, "repair_pressure": 0.0}

            created_at = node_data[0]
            # Simple temporal decay (more drift potential as symbol ages)
            # Days since creation
            try:
                from datetime import datetime

                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                days_old = (datetime.now() - created_dt.replace(tzinfo=None)).days
                decay = min(0.3, days_old / 365.0)  # Max 0.3 bonus from age (1 year)
            except Exception:
                decay = 0.0

            # Repair frequency spike
            # (Stub: in real system we would track history of repairs per symbol)
            return {
                "temporal_decay": round(decay, 4),
                "repair_pressure": 0.1,  # Placeholder
            }

    def _calculate_context_signals(self, symbol: str) -> dict[str, float]:
        """Layer C: Domain-aware sensitivity."""
        domain = symbol.split(".")[0] if "." in symbol else "agent"
        multiplier = DOMAIN_SENSITIVITY.get(domain, 1.0)
        return {"domain": domain, "sensitivity_multiplier": multiplier}

    def _record_drift_event(self, metrics: DriftMetrics):
        """Audit log for drift detection."""
        status = "STABLE"
        if metrics.final_score >= DRIFT_THRESHOLD_TRANSITION:
            status = "TRANSITION_REQUIRED"
        elif metrics.final_score >= DRIFT_THRESHOLD_OBSOLETE:
            status = "OBSOLETE_CANDIDATE"

        def _write(conn: sqlite3.Connection):
            conn.execute(
                """
                INSERT INTO symbol_drift_events (symbol, metrics_json, final_score, status)
                VALUES (?, ?, ?, ?)
            """,
                (metrics.symbol, metrics.to_json(), metrics.final_score, status),
            )

        self.brain._run_write_transaction(_write)

    def _generate_evolution_proposal(self, metrics: DriftMetrics):
        """Create a formal evolution proposal for human review."""
        # 1. Detect candidate symbol (best heuristic match for this cluster)
        with self.brain.get_connection(readonly=True) as conn:
            candidate_row = conn.execute(
                """
                SELECT chosen_symbol, COUNT(*) as freq, AVG(confidence) as conf
                FROM symbol_ambiguities
                WHERE chosen_symbol != ?
                  AND observation_id IN (SELECT id FROM observations WHERE symbol = ?)
                GROUP BY chosen_symbol
                ORDER BY freq DESC, conf DESC
                LIMIT 1
            """,
                (metrics.symbol, metrics.symbol),
            ).fetchone()

            if not candidate_row:
                return  # No strong candidate for evolution yet

            proposed_symbol, freq, conf = candidate_row

            # Only propose if confidence is reasonable
            if conf < 0.6:
                return

            # Check if proposal already exists
            existing = conn.execute(
                """
                SELECT id FROM symbol_reconciliation_proposals 
                WHERE symbol = ? AND proposed_symbol = ? AND status = 'pending'
            """,
                (metrics.symbol, proposed_symbol),
            ).fetchone()

            if existing:
                return

            rationale = {
                "drift_metrics": json.loads(metrics.to_json()),
                "evidence": f"Heuristic candidate '{proposed_symbol}' appeared {freq} times in ambiguities.",
                "why": [
                    "High lock violation rate detected.",
                    f"Strong semantic cluster found for alternative: {proposed_symbol}",
                    "Symbol age/decay suggests staleness.",
                ],
            }

            def _write(conn: sqlite3.Connection):
                conn.execute(
                    """
                    INSERT INTO symbol_reconciliation_proposals (symbol, proposed_symbol, confidence, rationale, status)
                    VALUES (?, ?, ?, ?, 'pending')
                """,
                    (metrics.symbol, proposed_symbol, conf, json.dumps(rationale)),
                )

            self.brain._run_write_transaction(_write)
            logger.info(f"SRE: Generated evolution proposal for '{metrics.symbol}' -> '{proposed_symbol}'")

    def evolve_symbol(self, proposal_id: int) -> bool:
        """
        Execute human-authorized symbol evolution.
        Creates an edge in the Evolution Graph.
        """
        try:
            with self.brain.get_connection(readonly=True) as conn:
                proposal = conn.execute(
                    "SELECT symbol, proposed_symbol, rationale FROM symbol_reconciliation_proposals WHERE id = ?",
                    (proposal_id,),
                ).fetchone()

            if not proposal:
                return False

            old_symbol, new_symbol, rationale = proposal

            def _execute(conn: sqlite3.Connection):
                # 1. Ensure both symbols exist in symbol_nodes
                conn.execute("INSERT OR IGNORE INTO symbol_nodes (symbol, locked) VALUES (?, 0)", (old_symbol,))
                conn.execute("INSERT OR IGNORE INTO symbol_nodes (symbol, locked) VALUES (?, 1)", (new_symbol,))

                # Get IDs
                old_id = conn.execute("SELECT id FROM symbol_nodes WHERE symbol = ?", (old_symbol,)).fetchone()[0]
                new_id = conn.execute("SELECT id FROM symbol_nodes WHERE symbol = ?", (new_symbol,)).fetchone()[0]

                # 2. Create Evolution Edge (Append-only)
                conn.execute(
                    """
                    INSERT INTO symbol_evolution_edges (from_symbol_id, to_symbol_id, relation_type, rationale_json)
                    VALUES (?, ?, 'supersedes', ?)
                """,
                    (old_id, new_id, rationale),
                )

                # 3. Update proposal status
                conn.execute(
                    "UPDATE symbol_reconciliation_proposals SET status = 'approved' WHERE id = ?", (proposal_id,)
                )

                # 4. Optional: Migration of old locked observations?
                # The user said: "KHÔNG nên update in-place... Chỉ được evolve via edge."
                # So we leave the old records with old symbol.
                # The search/recall engine should be updated to traverse the graph if needed.

            self.brain._run_write_transaction(_execute)
            return True
        except Exception as e:
            logger.error(f"SRE: Evolution failed for proposal {proposal_id}: {e}")
            return False
