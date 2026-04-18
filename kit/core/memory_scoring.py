# kit/core/memory_scoring.py
# v1.2.5 — Memory Fitness Function (Cognitive OS Survival Score)
#
# Philosophy:
#   Every memory must earn its place in the brain.
#   Scoring determines: keep, promote, or forget.
#
# Core Equation:
#   fitness_score = (utility × reusability × freshness) / (cost + entropy)
#
# Layer Eligibility:
#   - local_brain:      fitness > 0.3 (project-specific patterns)
#   - global_brain:     fitness > 0.6 AND cross_project_signal
#   - read_only:        fitness > 0.85 AND stable_over_time

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MemoryLayer(StrEnum):
    """Cognitive cortex layers (based on fitness threshold)."""
    WORKING = "working"        # Temporary (fitness < 0.3)
    LOCAL = "local"            # Project-scoped (0.3 ≤ fitness < 0.6)
    GLOBAL = "global"          # Cross-project (0.6 ≤ fitness < 0.85)
    FROZEN = "read_only"       # Immutable patterns (fitness ≥ 0.85)


@dataclass
class MemoryEventSignal:
    """Raw event from telemetry."""
    event_type: str             # recall, scan, learn, error, tool_usage
    symbol: str                 # thing being learned (class, function, module)
    frequency: int              # how many times seen
    success_rate: float         # 0.0 to 1.0
    cross_project_count: int    # how many projects use this pattern
    recency: float              # days since last seen
    context_richness: int       # how much detail captured (entropy inverse)
    error_type: str | None      # if event_type="error", what kind
    metadata: dict[str, Any]    # arbitrary signal


@dataclass
class MemoryScore:
    """Scoring breakdown for transparency."""
    fitness: float              # 0.0 to 1.0 (main score)
    utility: float              # how often used (frequency signal)
    reusability: float          # can others benefit (cross-project signal)
    freshness: float            # recency decay
    cost: float                 # storage/lookup cost
    entropy: float              # complexity cost
    confidence: float           # how sure about this memory
    layer: MemoryLayer          # recommended layer


class MemoryFitnessEngine:
    """
    Cognitive fitness scorer.
    
    Determines what memories are worth keeping and where they should live.
    This is the learning policy for the entire KIT system.
    """
    
    # Thresholds (layer boundaries)
    THRESHOLD_LOCAL = 0.30          # Minimum to store locally
    THRESHOLD_GLOBAL = 0.60         # Promote to global brain
    THRESHOLD_FROZEN = 0.85         # Promote to read-only (immutable)
    
    # Memoization/caching (to avoid re-computing fitness)
    _score_cache: dict[str, MemoryScore] = {}
    
    def score_event(self, signal: MemoryEventSignal) -> MemoryScore:
        """
        Main entry point: transform telemetry signal → fitness score.
        
        Returns MemoryScore with layer recommendation.
        """
        
        # 1. UTILITY (how often is this used?)
        utility = self._score_utility(signal.frequency, signal.success_rate)
        
        # 2. REUSABILITY (can other projects benefit?)
        reusability = self._score_reusability(signal.cross_project_count)
        
        # 3. FRESHNESS (is it still relevant?)
        freshness = self._score_freshness(signal.recency)
        
        # 4. COST (how expensive to store/lookup?)
        cost = self._score_cost(signal.context_richness)
        
        # 5. ENTROPY (is it too complex/noisy?)
        entropy = self._score_entropy(signal.metadata)
        
        # 6. CONFIDENCE (how sure are we?)
        confidence = self._score_confidence(signal)
        
        # MAIN FITNESS EQUATION
        # Utility × Reusability × Freshness (numerator)
        # Cost + Entropy (denominator - regulatory factor)
        numerator = utility * reusability * freshness
        denominator = max(0.1, cost + entropy)  # Prevent division by zero
        
        fitness = numerator / denominator
        fitness = min(1.0, max(0.0, fitness))  # Clamp to [0.0, 1.0]
        
        # Determine recommended layer
        if fitness >= self.THRESHOLD_FROZEN:
            layer = MemoryLayer.FROZEN
        elif fitness >= self.THRESHOLD_GLOBAL:
            layer = MemoryLayer.GLOBAL
        elif fitness >= self.THRESHOLD_LOCAL:
            layer = MemoryLayer.LOCAL
        else:
            layer = MemoryLayer.WORKING
        
        return MemoryScore(
            fitness=fitness,
            utility=utility,
            reusability=reusability,
            freshness=freshness,
            cost=cost,
            entropy=entropy,
            confidence=confidence,
            layer=layer,
        )
    
    @staticmethod
    def _score_utility(frequency: int, success_rate: float) -> float:
        """
        How often is this pattern actually used and does it work?
        
        Logic:
        - frequency > 5: high utility (proven useful)
        - success_rate > 0.8: high reliability
        """
        # Normalize frequency (log scale, 1-10+ becomes 0.0-1.0)
        freq_score = min(1.0, math.log1p(frequency) / math.log1p(10))
        
        # Success rate directly maps to reliability
        success_score = success_rate
        
        # Combine: success rate matters more if frequency is high
        utility = (freq_score * 0.4) + (success_score * 0.6)
        
        return utility
    
    @staticmethod
    def _score_reusability(cross_project_count: int) -> float:
        """
        Can other projects benefit from this pattern?
        
        Logic:
        - 1 project (yours only) = 0.3 (low reusability)
        - 2+ projects = 0.6 (medium, cross-project validation)
        - 5+ projects = 0.9 (high, universal pattern)
        """
        if cross_project_count <= 1:
            return 0.3  # Locally useful only
        elif cross_project_count == 2:
            return 0.6  # Some cross-project relevance
        elif cross_project_count >= 5:
            return 0.9  # Universal pattern
        else:
            # Linear interpolation for 3-4 projects
            return 0.3 + ((cross_project_count - 1) / 4) * 0.6
    
    @staticmethod
    def _score_freshness(recency_days: float) -> float:
        """
        How recent is this pattern?
        
        Decay model (exponential):
        - 0 days ago = 1.0
        - 30 days ago = 0.5
        - 90 days ago = 0.1
        - 365 days ago = 0.01
        """
        # Half-life of 30 days
        decay_half_life = 30.0
        freshness = math.exp(-0.693 * (recency_days / decay_half_life))
        return min(1.0, freshness)
    
    @staticmethod
    def _score_cost(context_richness: int) -> float:
        """
        Storage and lookup cost.
        
        Logic:
        - More context = higher cost
        - context_richness 10+ = 0.3 cost (expensive but worth it)
        - context_richness 1-5 = 0.8 cost (cheap patterns)
        """
        # Normalize richness (1-20 becomes a cost score)
        # Higher richness = lower cost (paradoxically good - more info)
        if context_richness < 1:
            return 1.0  # Empty context is waste
        cost = max(0.1, 1.0 - (min(context_richness, 20) / 20) * 0.7)
        return cost
    
    @staticmethod
    def _score_entropy(metadata: dict[str, Any]) -> float:
        """
        Complexity/noise of the pattern.
        
        High entropy = fuzzy/noisy pattern = hard to reuse
        Low entropy = clear/crisp pattern = easy to reuse
        """
        if not metadata:
            return 0.0
        
        # Heuristics for entropy
        entropy = 0.0
        
        # Too many variants of same thing? High entropy.
        if "variants" in metadata:
            variants = metadata["variants"]
            if isinstance(variants, (list, int)):
                count = len(variants) if isinstance(variants, list) else variants
                entropy += min(0.3, count / 10)
        
        # Multiple error modes? High entropy.
        if "error_count" in metadata:
            errors = metadata["error_count"]
            entropy += min(0.3, errors / 10)
        
        # Unclear dependencies? High entropy.
        if "dependency_count" in metadata:
            deps = metadata["dependency_count"]
            entropy += min(0.4, deps / 20)
        
        return min(1.0, entropy)
    
    @staticmethod
    def _score_confidence(signal: MemoryEventSignal) -> float:
        """
        How confident are we in this memory?
        
        Based on:
        - Success rate (high success = high confidence)
        - Frequency (more observations = higher confidence)
        - Error type (errors reduce confidence)
        """
        base_confidence = signal.success_rate
        
        # Boost confidence if seen many times
        frequency_boost = min(0.2, math.log1p(signal.frequency) / math.log1p(20))
        
        # Reduce if there were errors
        error_penalty = 0.2 if signal.error_type else 0.0
        
        confidence = base_confidence + frequency_boost - error_penalty
        return min(1.0, max(0.0, confidence))


class MemoryPromotionPolicy:
    """
    Rules for moving memories between layers.
    
    This prevents bloat and ensures high-quality knowledge propagates.
    """
    
    # Promotion criteria (must meet ALL to promote)
    LOCAL_TO_GLOBAL = {
        "min_fitness": 0.60,
        "min_frequency": 5,
        "min_success_rate": 0.80,
        "min_cross_project": 2,  # Must work across projects
        "max_error_rate": 0.20,
    }
    
    GLOBAL_TO_FROZEN = {
        "min_fitness": 0.85,
        "min_frequency": 20,
        "min_success_rate": 0.95,
        "min_cross_project": 5,  # Must work across 5+ projects
        "max_error_rate": 0.05,
        "min_stability_days": 90,  # Must be stable for 3 months
    }
    
    @classmethod
    def should_promote_to_global(cls, score: MemoryScore, signal: MemoryEventSignal) -> bool:
        """Check if memory should move from local_brain to global_brain."""
        policy = cls.LOCAL_TO_GLOBAL
        
        return (
            score.fitness >= policy["min_fitness"]
            and signal.frequency >= policy["min_frequency"]
            and signal.success_rate >= policy["min_success_rate"]
            and signal.cross_project_count >= policy["min_cross_project"]
            and (1.0 - signal.success_rate) <= policy["max_error_rate"]
        )
    
    @classmethod
    def should_promote_to_frozen(cls, score: MemoryScore, signal: MemoryEventSignal, 
                                  days_in_global: float) -> bool:
        """Check if memory should move from global_brain to read_only."""
        policy = cls.GLOBAL_TO_FROZEN
        
        return (
            score.fitness >= policy["min_fitness"]
            and signal.frequency >= policy["min_frequency"]
            and signal.success_rate >= policy["min_success_rate"]
            and signal.cross_project_count >= policy["min_cross_project"]
            and (1.0 - signal.success_rate) <= policy["max_error_rate"]
            and days_in_global >= policy["min_stability_days"]
        )


# Example usage (for testing/validation)
if __name__ == "__main__":
    engine = MemoryFitnessEngine()
    
    # Test: a pattern seen 3 times, success_rate 0.9, used in 2 projects, 5 days old
    test_signal = MemoryEventSignal(
        event_type="recall",
        symbol="AuthenticationMiddleware",
        frequency=3,
        success_rate=0.90,
        cross_project_count=2,
        recency=5.0,
        context_richness=8,
        error_type=None,
        metadata={},
    )
    
    score = engine.score_event(test_signal)
    
    print(f"Pattern: {test_signal.symbol}")
    print(f"Fitness: {score.fitness:.3f}")
    print(f"Recommended layer: {score.layer}")
    print(f"  - Utility: {score.utility:.3f}")
    print(f"  - Reusability: {score.reusability:.3f}")
    print(f"  - Freshness: {score.freshness:.3f}")
    print(f"  - Cost: {score.cost:.3f}")
    print(f"  - Entropy: {score.entropy:.3f}")
    print(f"  - Confidence: {score.confidence:.3f}")
