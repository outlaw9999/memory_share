import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    """
    AMSB Model Performance Metrics (v3.14 Doctrine).
    Thread-safe by design (immutable), persistence via external storage.
    """

    name: str
    cost_per_1k: float = 0.0
    trust_score: float = 1.0
    avg_latency: float = 1.0
    failures: int = 0
    blocks: int = 0
    successes: int = 0
    last_updated: float = field(default_factory=time.time)
    healthy: bool = True
    last_error_type: str | None = None

    def get_effective_trust(self) -> float:
        """Patch 3: Time-decay trust (10% decay per hour)."""
        now = time.time()
        age_hours = (now - self.last_updated) / 3600
        decay_factor = 0.9**age_hours

        total = self.successes + self.failures + self.blocks
        if total == 0:
            return 1.0 * decay_factor

        success_rate = self.successes / total
        # Blocks represent model logic failures (heavy penalty)
        block_penalty = (self.blocks * 0.5) / total

        base_trust = max(0.1, success_rate - block_penalty)
        return base_trust * decay_factor

    def calculate_score(self) -> float:
        """
        Adaptive Scoring: multi-objective decision system.
        Weights: Trust (60%), Latency (20%), Cost (20%)
        """
        trust = self.get_effective_trust()

        # Normalize latency (log scale, lower is better)
        import math

        latency_penalty = math.log10(self.avg_latency + 1.1) * 0.2

        # Cost penalty (scaled)
        cost_penalty = (self.cost_per_1k * 10.0) * 0.2

        return (trust * 0.6) - latency_penalty - cost_penalty

    def cooldown_active(self) -> bool:
        """
        Stateful Short-Circuit with Severity Awareness.
        CAPACITY (503) -> 15 min
        TIMEOUT -> 30 sec
        DEFAULT -> 5 min exponential
        """
        if self.healthy:
            return False

        now = time.time()
        elapsed = now - self.last_updated

        if self.last_error_type == "CAPACITY":
            return elapsed < 900  # 15 minutes
        if self.last_error_type == "TIMEOUT":
            return elapsed < 30  # 30 seconds

        # Standard Exponential Backoff
        wait_time = min(1800, 30 * (2 ** (self.failures - 2)))
        return elapsed < wait_time

    def with_update(self, success: bool, latency: float, error_type: str | None = None, is_block: bool = False) -> Self:
        """Functional update (returns new immutable instance)."""
        new_failures = 0 if success else (self.failures + 1)
        new_healthy = True if success else (error_type != "CAPACITY" and new_failures < 2)

        # Exponential moving average for latency
        new_avg_latency = (0.7 * self.avg_latency) + (0.3 * latency) if success else self.avg_latency

        return ModelMetrics(
            name=self.name,
            cost_per_1k=self.cost_per_1k,
            successes=self.successes + (1 if success else 0),
            failures=new_failures,
            blocks=self.blocks + (1 if is_block else 0),
            avg_latency=new_avg_latency,
            last_updated=time.time(),
            healthy=new_healthy,
            last_error_type=error_type if not success else None,
            trust_score=0.0,  # Will be recalculated by get_effective_trust
        )


class MetricsPersistence:
    """SQLite-based persistence for ModelMetrics."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_table()

    def _init_table(self):
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_metrics (
                    name TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

    def save(self, metrics: ModelMetrics):
        import json

        data = {
            "successes": metrics.successes,
            "failures": metrics.failures,
            "blocks": metrics.blocks,
            "avg_latency": metrics.avg_latency,
            "last_updated": metrics.last_updated,
            "healthy": metrics.healthy,
            "last_error_type": metrics.last_error_type,
        }
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            conn.execute(
                "INSERT INTO agent_metrics (name, data, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (metrics.name, json.dumps(data), time.time()),
            )

    def load_all(self, registry: dict[str, ModelMetrics]) -> dict[str, ModelMetrics]:
        import json

        results = {**registry}
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT name, data FROM agent_metrics").fetchall()
                for row in rows:
                    name = row["name"]
                    if name in registry:
                        data = json.loads(row["data"])
                        results[name] = ModelMetrics(
                            name=name,
                            cost_per_1k=registry[name].cost_per_1k,
                            successes=data["successes"],
                            failures=data["failures"],
                            blocks=data["blocks"],
                            avg_latency=data["avg_latency"],
                            last_updated=data["last_updated"],
                            healthy=data["healthy"],
                            last_error_type=data.get("last_error_type"),
                        )
        except sqlite3.Error:
            pass  # Doctrine: Fallback to defaults if DB locked or missing
        return results
