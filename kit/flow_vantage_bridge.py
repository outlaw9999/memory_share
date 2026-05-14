#!/usr/bin/env python3
"""
Flow-Vantage Feedback Bridge v1.2.5

Implements the learning loop: Flow → Execute → Observe → Vantage → Adjust Flow

This bridge enables the system to evolve from deterministic to adaptive routing.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from kit.api import get_brain, resolve_paths


@dataclass
class FlowDecision:
    """Represents a routing decision made by the flow."""

    signal_id: str
    route_taken: str
    priority: float
    timestamp: str
    outcome: str | None = None
    vantage_score: float | None = None


@dataclass
class VantageSignal:
    """Vantage analysis of a flow decision."""

    decision_id: str
    friction_detected: bool
    improvement_suggestions: list[str]
    confidence_score: float
    learning_weight: float


class FlowVantageBridge:
    """Bridge between Flow execution and Vantage learning."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            _, project_db, _ = resolve_paths()
            self.db_path = project_db
        else:
            self.db_path = db_path

        self._init_db()

    def _get_conn(self, readonly: bool = False):
        """Unified connection authority (v1.2.5-TITANIUM)."""
        return get_brain().get_connection(self.db_path, readonly=readonly)

    def _init_db(self):
        """Initialize the learning database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_conn(readonly=False) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_decisions (
                    id TEXT PRIMARY KEY,
                    signal_id TEXT,
                    route_taken TEXT,
                    priority REAL,
                    timestamp TEXT,
                    outcome TEXT,
                    vantage_score REAL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS vantage_signals (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT,
                    friction_detected BOOLEAN,
                    suggestions TEXT,  -- JSON array
                    confidence_score REAL,
                    learning_weight REAL,
                    timestamp TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS routing_weights (
                    route TEXT PRIMARY KEY,
                    base_weight REAL DEFAULT 1.0,
                    learned_weight REAL DEFAULT 0.0,
                    success_rate REAL DEFAULT 0.5,
                    total_decisions INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            """)

    def record_decision(self, decision: FlowDecision):
        """Record a flow routing decision."""
        with self._get_conn(readonly=False) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO flow_decisions
                (id, signal_id, route_taken, priority, timestamp, outcome, vantage_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"{decision.signal_id}_{decision.timestamp}",
                    decision.signal_id,
                    decision.route_taken,
                    decision.priority,
                    decision.timestamp,
                    decision.outcome,
                    decision.vantage_score,
                ),
            )

    def record_vantage_analysis(self, signal: VantageSignal):
        """Record Vantage analysis of a decision."""
        with self._get_conn(readonly=False) as conn:
            conn.execute(
                """
                INSERT INTO vantage_signals
                (id, decision_id, friction_detected, suggestions, confidence_score, learning_weight, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"{signal.decision_id}_vantage_{datetime.now().isoformat()}",
                    signal.decision_id,
                    signal.friction_detected,
                    json.dumps(signal.improvement_suggestions),
                    signal.confidence_score,
                    signal.learning_weight,
                    datetime.now().isoformat(),
                ),
            )

    def update_routing_weights(self):
        """Update routing weights based on historical performance and Vantage feedback."""
        with self._get_conn(readonly=False) as conn:
            # Calculate success rates and learning adjustments
            decisions = conn.execute("""
                SELECT route_taken, outcome, vantage_score
                FROM flow_decisions
                WHERE outcome IS NOT NULL
            """).fetchall()

            route_stats = {}
            for route, outcome, vantage_score in decisions:
                if route not in route_stats:
                    route_stats[route] = {"total": 0, "success": 0, "vantage_sum": 0}

                route_stats[route]["total"] += 1
                if outcome == "success":
                    route_stats[route]["success"] += 1
                if vantage_score:
                    route_stats[route]["vantage_sum"] += vantage_score

            # Update weights
            for route, stats in route_stats.items():
                success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0.5
                avg_vantage = stats["vantage_sum"] / stats["total"] if stats["total"] > 0 else 0.0

                # Learning adjustment: higher success + better vantage = higher weight
                learned_weight = (success_rate - 0.5) + (avg_vantage * 0.1)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO routing_weights
                    (route, success_rate, learned_weight, total_decisions, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (route, success_rate, learned_weight, stats["total"], datetime.now().isoformat()),
                )

    def get_adaptive_route(self, signal: dict[str, Any], base_routes: list[str]) -> str:
        """Get the best route considering historical learning."""
        self.update_routing_weights()  # Ensure weights are current

        with self._get_conn(readonly=False) as conn:
            weights = {}
            for route in base_routes:
                row = conn.execute(
                    """
                    SELECT base_weight, learned_weight, success_rate
                    FROM routing_weights
                    WHERE route = ?
                """,
                    (route,),
                ).fetchone()

                if row:
                    base_w, learned_w, success_r = row
                    weights[route] = base_w + learned_w + (success_r * 0.2)
                else:
                    weights[route] = 1.0  # Default weight

        # Select route with highest weight, with signal priority as tiebreaker
        signal_priority = signal.get("importance", 0.5)
        best_route = max(weights.keys(), key=lambda r: (weights[r], signal_priority))

        return best_route

    def get_learning_insights(self) -> dict[str, Any]:
        """Get insights into the learning progress."""
        self.update_routing_weights()  # Ensure weights are current

        with self._get_conn(readonly=False) as conn:
            total_decisions = conn.execute("SELECT COUNT(*) FROM flow_decisions").fetchone()[0]
            total_vantage = conn.execute("SELECT COUNT(*) FROM vantage_signals").fetchone()[0]

            route_performance = conn.execute("""
                SELECT route, success_rate, learned_weight, total_decisions
                FROM routing_weights
                ORDER BY learned_weight DESC
            """).fetchall()

        return {
            "total_decisions": total_decisions,
            "total_vantage_analyses": total_vantage,
            "route_performance": [
                {"route": r, "success_rate": sr, "learned_weight": lw, "total_decisions": td}
                for r, sr, lw, td in route_performance
            ],
        }

    def simulate_feedback_loop(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Simulate a complete feedback loop for testing."""
        # Record decision
        decision = FlowDecision(
            signal_id=signal.get("id", "test_signal"),
            route_taken="simulated_route",
            priority=signal.get("importance", 0.5),
            timestamp=datetime.now().isoformat(),
            outcome="success",  # Simulate success
        )
        self.record_decision(decision)

        # Simulate Vantage analysis
        vantage = VantageSignal(
            decision_id=f"{decision.signal_id}_{decision.timestamp}",
            friction_detected=False,
            improvement_suggestions=["Consider higher priority for similar signals"],
            confidence_score=0.85,
            learning_weight=0.1,
        )
        self.record_vantage_analysis(vantage)

        # Update weights
        self.update_routing_weights()

        # Get insights
        insights = self.get_learning_insights()

        return {
            "decision": decision.__dict__,
            "vantage": {
                "friction_detected": vantage.friction_detected,
                "suggestions": vantage.improvement_suggestions,
                "confidence": vantage.confidence_score,
            },
            "insights": insights,
        }


# Global bridge instance
_bridge_instance: FlowVantageBridge | None = None


def get_bridge() -> FlowVantageBridge:
    """Get the global feedback bridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = FlowVantageBridge()
    return _bridge_instance
