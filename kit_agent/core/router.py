import random
from typing import Dict, List, Optional
from kit_agent.core.metrics import ModelMetrics, MetricsPersistence

class ModelRouter:
    def __init__(self, models: Dict[str, ModelMetrics], persistence: MetricsPersistence | None = None, epsilon: float = 0.1):
        self.models = models
        self.persistence = persistence
        self.epsilon = epsilon # 10% Exploration

    def update_model(self, name: str, success: bool, latency: float, error_type: str | None = None, is_block: bool = False):
        if name in self.models:
            updated = self.models[name].with_update(success, latency, error_type, is_block)
            self.models[name] = updated
            if self.persistence:
                self.persistence.save(updated)

    def _calculate_effective_score(self, name: str) -> float:
        """
        Adaptive Scoring: Trust (60%), Latency (20%), Cost (20%)
        """
        m = self.models[name]
        return m.calculate_score()

    def select(self, task_type: str = "general") -> str:
        """
        Adaptive Selection with Patch 4 (Exploration)
        """
        candidates = [
            name for name, m in self.models.items() 
            if not m.cooldown_active()
        ]
        
        if not candidates:
            if "local" in self.models:
                return "local"
            return min(
                self.models,
                key=lambda name: (
                    self.models[name].failures,
                    -self.models[name].get_effective_trust(),
                    self.models[name].avg_latency,
                ),
            )

        # Task-specific overrides
        if task_type == "simple" and "local" in candidates:
            # Randomly favor local for simple tasks to save cost
            if random.random() < 0.7:
                return "local"

        # Patch 4: Epsilon-Greedy Exploration
        if random.random() < self.epsilon:
            return random.choice(candidates)

        # Exploitation: Select best effective score
        best_model = max(candidates, key=lambda n: self._calculate_effective_score(n))
        return best_model
