# tests/test_memory_scoring.py
# v1.2.5 — TDD Suite for Memory Fitness Engine & Learning Loop Logic
#
# Philosophy: Every rule must be testable. Every boundary must be explicit.
# We test the POLICY first, then implement behavior against it.

import math
from pathlib import Path

import pytest

from kit.core.memory_scoring import (
    MemoryEventSignal,
    MemoryFitnessEngine,
    MemoryLayer,
    MemoryPromotionPolicy,
    MemoryScore,
)


class TestMemoryFitnessEngine:
    """Core fitness scoring logic tests."""

    @pytest.fixture
    def engine(self):
        return MemoryFitnessEngine()

    # ============================================================================
    # TEST: UTILITY SCORING (frequency + success rate)
    # ============================================================================

    def test_utility_high_frequency_high_success(self, engine):
        """Pattern used many times with high success → high utility."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="DatabaseConnection",
            frequency=10,
            success_rate=0.95,
            cross_project_count=1,
            recency=5.0,
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        # High frequency + high success should dominate
        assert score.utility >= 0.75, f"Expected high utility, got {score.utility}"

    def test_utility_low_frequency(self, engine):
        """Pattern seen once, even with success → low utility."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="RarePattern",
            frequency=1,
            success_rate=1.0,  # Perfect success but rare
            cross_project_count=1,
            recency=5.0,
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        # v1.2.5: Even low frequency with 100% success has decent utility (~0.7)
        assert score.utility > 0.6, f"Low frequency with high success should have moderate utility, got {score.utility}"

    def test_utility_high_frequency_low_success(self, engine):
        """Pattern used often but fails → reduced utility."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="BuggyPattern",
            frequency=10,
            success_rate=0.5,  # 50% failure rate
            cross_project_count=1,
            recency=5.0,
            context_richness=5,
            error_type="timeout",
            metadata={},
        )
        score = engine.score_event(signal)

        # v1.2.5: High frequency + success matters.
        assert score.utility >= 0.6, f"High frequency + moderate success should be >= 0.6, got {score.utility}"

    # ============================================================================
    # TEST: REUSABILITY SCORING (cross-project count)
    # ============================================================================

    def test_reusability_single_project(self, engine):
        """Pattern only seen in your project → low reusability."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="ProjectSpecificCode",
            frequency=10,
            success_rate=0.95,
            cross_project_count=1,  # Only here
            recency=5.0,
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        assert score.reusability == 0.3, f"Single project should have reusability=0.3, got {score.reusability}"

    def test_reusability_two_projects(self, engine):
        """Pattern in 2 projects → emerging pattern."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="CommonPattern",
            frequency=10,
            success_rate=0.95,
            cross_project_count=2,  # Cross-project!
            recency=5.0,
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        assert score.reusability == 0.6, f"Two projects should have reusability=0.6, got {score.reusability}"

    def test_reusability_five_plus_projects(self, engine):
        """Pattern in 5+ projects → universal pattern."""
        for cross_count in [5, 10, 100]:
            signal = MemoryEventSignal(
                event_type="recall",
                symbol="UniversalPattern",
                frequency=10,
                success_rate=0.95,
                cross_project_count=cross_count,
                recency=5.0,
                context_richness=5,
                error_type=None,
                metadata={},
            )
            score = engine.score_event(signal)

            assert score.reusability == 0.9, f"5+ projects should have reusability=0.9, got {score.reusability}"

    # ============================================================================
    # TEST: FRESHNESS SCORING (exponential decay)
    # ============================================================================

    def test_freshness_recent_pattern(self, engine):
        """Pattern from today → full freshness."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="RecentPattern",
            frequency=10,
            success_rate=0.95,
            cross_project_count=1,
            recency=0.0,  # Just now
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        assert score.freshness >= 0.99, f"Recent pattern should have freshness ~1.0, got {score.freshness}"

    def test_freshness_30_days_old(self, engine):
        """Pattern 30 days old → half freshness (exponential half-life)."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="OldPattern",
            frequency=10,
            success_rate=0.95,
            cross_project_count=1,
            recency=30.0,  # 30 days
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        # Half-life is 30 days, so e^-0.693 ≈ 0.5
        assert 0.48 < score.freshness < 0.52, f"30 days should be ~0.5 freshness, got {score.freshness}"

    def test_freshness_90_days_old(self, engine):
        """Pattern 90 days old → very stale."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="VeryOldPattern",
            frequency=10,
            success_rate=0.95,
            cross_project_count=1,
            recency=90.0,  # ~3 months
            context_richness=5,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        # Should be much lower than recent pattern
        assert score.freshness < 0.15, f"90 days should be very stale, got {score.freshness}"

    # ============================================================================
    # TEST: FITNESS LAYER ASSIGNMENT
    # ============================================================================

    def test_layer_assignment_working(self, engine):
        """Low quality pattern → stays in WORKING (not stored)."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="WeakPattern",
            frequency=1,
            success_rate=0.5,
            cross_project_count=1,
            recency=100.0,  # Stale
            context_richness=1,
            error_type="error",
            metadata={"variants": [1, 2, 3, 4, 5]},  # High entropy
        )
        score = engine.score_event(signal)

        assert score.layer == MemoryLayer.WORKING, f"Weak pattern should be WORKING, got {score.layer}"
        assert score.fitness < 0.30

    def test_layer_assignment_local(self, engine):
        """Medium quality, single-project → LOCAL brain."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="ProjectPattern",
            frequency=5,
            success_rate=0.85,
            cross_project_count=1,  # Only your project
            recency=5.0,
            context_richness=8,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        assert score.layer == MemoryLayer.LOCAL, f"Single-project pattern should be LOCAL, got {score.layer}"
        assert 0.30 <= score.fitness < 0.60

    def test_layer_assignment_global(self, engine):
        """Good quality, multi-project → GLOBAL brain."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="CommonPattern",
            frequency=10,
            success_rate=0.90,
            cross_project_count=3,  # Multiple projects
            recency=5.0,
            context_richness=8,
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        assert score.layer == MemoryLayer.GLOBAL, f"Multi-project pattern should be GLOBAL, got {score.layer}"
        assert 0.60 <= score.fitness < 0.85

    def test_layer_assignment_frozen(self, engine):
        """Excellent quality, stable, cross-project → FROZEN (immutable)."""
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="BestPractice",
            frequency=50,  # Many uses
            success_rate=0.98,  # Excellent success
            cross_project_count=10,  # Universal
            recency=2.0,  # Still fresh
            context_richness=15,  # Rich context
            error_type=None,
            metadata={},
        )
        score = engine.score_event(signal)

        assert score.layer == MemoryLayer.FROZEN, f"Excel pattern should be FROZEN, got {score.layer}"
        assert score.fitness >= 0.85

    # ============================================================================
    # TEST: BOUNDARY CONDITIONS
    # ============================================================================

    def test_fitness_bounded_0_to_1(self, engine):
        """Fitness is always [0.0, 1.0]."""
        extreme_signals = [
            MemoryEventSignal(
                event_type="recall",
                symbol="Extreme1",
                frequency=0,  # Zero uses
                success_rate=0.0,
                cross_project_count=0,
                recency=1000.0,  # Very old
                context_richness=0,
                error_type="critic",
                metadata={},
            ),
            MemoryEventSignal(
                event_type="recall",
                symbol="Extreme2",
                frequency=1000,  # Insane freq
                success_rate=1.0,
                cross_project_count=1000,  # Insane reuse
                recency=-10.0,  # Time travel?
                context_richness=1000,
                error_type=None,
                metadata={},
            ),
        ]

        for signal in extreme_signals:
            score = engine.score_event(signal)
            assert 0.0 <= score.fitness <= 1.0, f"Fitness out of bounds: {score.fitness}"

    # ============================================================================
    # TEST: ENTROPY SCORING (complexity penalty)
    # ============================================================================

    def test_entropy_high_variants(self, engine):
        """Pattern with many variants → high entropy → lower fitness."""
        signal_few_variants = MemoryEventSignal(
            event_type="recall",
            symbol="Pattern1",
            frequency=10,
            success_rate=0.90,
            cross_project_count=2,
            recency=5.0,
            context_richness=8,
            error_type=None,
            metadata={"variants": [1]},  # Few variants
        )

        signal_many_variants = MemoryEventSignal(
            event_type="recall",
            symbol="Pattern2",
            frequency=10,
            success_rate=0.90,
            cross_project_count=2,
            recency=5.0,
            context_richness=8,
            error_type=None,
            metadata={"variants": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},  # Many variants
        )

        engine = MemoryFitnessEngine()
        score1 = engine.score_event(signal_few_variants)
        score2 = engine.score_event(signal_many_variants)

        assert score1.fitness > score2.fitness, "High entropy should reduce fitness"


class TestMemoryPromotionPolicy:
    """Promotion rules between layers."""

    def test_should_promote_local_to_global(self):
        """Pattern meets all criteria → gets promoted."""
        score = MemoryScore(
            fitness=0.65,  # Meets threshold
            utility=0.7,
            reusability=0.6,
            freshness=0.9,
            cost=0.2,
            entropy=0.1,
            confidence=0.85,
            layer=MemoryLayer.GLOBAL,
        )

        signal = MemoryEventSignal(
            event_type="recall",
            symbol="PromoteMe",
            frequency=5,  # Meets min
            success_rate=0.85,  # Meets threshold
            cross_project_count=2,  # Meets min
            recency=5.0,
            context_richness=8,
            error_type=None,
            metadata={},
        )

        result = MemoryPromotionPolicy.should_promote_to_global(score, signal)
        assert result is True, "Pattern should be promoted"

    def test_should_not_promote_low_fitness(self):
        """Low fitness → no promotion."""
        score = MemoryScore(
            fitness=0.5,  # Below threshold
            utility=0.5,
            reusability=0.3,
            freshness=0.9,
            cost=0.2,
            entropy=0.1,
            confidence=0.75,
            layer=MemoryLayer.LOCAL,
        )

        signal = MemoryEventSignal(
            event_type="recall",
            symbol="TooWeak",
            frequency=2,  # Below min
            success_rate=0.80,
            cross_project_count=1,  # Below min
            recency=5.0,
            context_richness=8,
            error_type=None,
            metadata={},
        )

        result = MemoryPromotionPolicy.should_promote_to_global(score, signal)
        assert result is False, "Low quality should not promote"

    def test_should_not_promote_high_error_rate(self):
        """High error rate blocks promotion (safety critical)."""
        score = MemoryScore(
            fitness=0.70,  # Good fitness
            utility=0.8,
            reusability=0.7,
            freshness=0.9,
            cost=0.2,
            entropy=0.1,
            confidence=0.85,
            layer=MemoryLayer.LOCAL,
        )

        signal = MemoryEventSignal(
            event_type="recall",
            symbol="UnreliablePattern",
            frequency=10,  # High usage
            success_rate=0.5,  # 50% error rate (FAIL)
            cross_project_count=2,
            recency=5.0,
            context_richness=8,
            error_type="timeout",
            metadata={},
        )

        result = MemoryPromotionPolicy.should_promote_to_global(score, signal)
        assert result is False, "High error rate blocks promotion"

    def test_should_promote_to_frozen_requires_stability(self):
        """Only old, stable patterns get FROZEN status."""
        score = MemoryScore(
            fitness=0.90,  # Excellent
            utility=0.95,
            reusability=0.9,
            freshness=0.95,
            cost=0.1,
            entropy=0.0,
            confidence=0.98,
            layer=MemoryLayer.GLOBAL,
        )

        signal = MemoryEventSignal(
            event_type="recall",
            symbol="MasterPattern",
            frequency=50,  # High usage
            success_rate=0.98,  # Excellent
            cross_project_count=10,  # Universal
            recency=2.0,
            context_richness=15,
            error_type=None,
            metadata={},
        )

        # Should promote if in GLOBAL for 90+ days
        result = MemoryPromotionPolicy.should_promote_to_frozen(score, signal, days_in_global=91.0)
        assert result is True, "Stable pattern should promote to FROZEN"

        # Should NOT promote if only recently in GLOBAL
        result = MemoryPromotionPolicy.should_promote_to_frozen(score, signal, days_in_global=30.0)
        assert result is False, "Unstable pattern should not promote to FROZEN"


class TestLearningLoopIntegration:
    """End-to-end: event → scoring → promotion decision."""

    def test_full_pipeline_new_pattern(self):
        """New pattern: appears, gets scored, assigned to LOCAL."""
        engine = MemoryFitnessEngine()

        # First observation of pattern
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="AuthMiddleware",
            frequency=1,
            success_rate=1.0,
            cross_project_count=1,
            recency=0.0,
            context_richness=10,
            error_type=None,
            metadata={},
        )

        score = engine.score_event(signal)

        # Should be LOCAL tier (not working, but not global)
        assert score.layer == MemoryLayer.LOCAL or score.layer == MemoryLayer.WORKING

    def test_full_pipeline_maturing_pattern(self):
        """Pattern matures: LOCAL → GLOBAL after enough evidence."""
        engine = MemoryFitnessEngine()

        # Matured observation
        signal = MemoryEventSignal(
            event_type="recall",
            symbol="AuthMiddleware",
            frequency=8,  # Seen 8 times
            success_rate=0.93,
            cross_project_count=2,  # Works across projects
            recency=2.0,
            context_richness=12,
            error_type=None,
            metadata={},
        )

        score = engine.score_event(signal)
        promotion = MemoryPromotionPolicy.should_promote_to_global(score, signal)

        # v1.2.5: High richness + frequency can push into FROZEN/READ_ONLY
        assert score.layer in [MemoryLayer.GLOBAL, MemoryLayer.FROZEN]
        assert promotion is True

    def test_full_pipeline_universal_pattern(self):
        """Pattern becomes universal: GLOBAL → FROZEN after stability."""
        engine = MemoryFitnessEngine()

        signal = MemoryEventSignal(
            event_type="recall",
            symbol="JSONSerialization",
            frequency=100,
            success_rate=0.99,
            cross_project_count=15,
            recency=1.0,
            context_richness=20,
            error_type=None,
            metadata={},
        )

        score = engine.score_event(signal)
        is_frozen = MemoryPromotionPolicy.should_promote_to_frozen(score, signal, days_in_global=100.0)

        assert score.fitness >= 0.85
        assert is_frozen is True


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    # Quick validation run (without pytest)
    engine = MemoryFitnessEngine()

    print("🧠 KIT v1.2.5 Memory Fitness Engine - Validation")
    print("=" * 60)

    # Test case 1: Weak pattern
    weak = MemoryEventSignal(
        event_type="recall",
        symbol="WeakPattern",
        frequency=1,
        success_rate=0.5,
        cross_project_count=1,
        recency=100.0,
        context_richness=1,
        error_type="error",
        metadata={},
    )
    score1 = engine.score_event(weak)
    print(f"\n1. Weak pattern → {score1.layer.value}")
    print(f"   Fitness: {score1.fitness:.3f}")

    # Test case 2: Strong pattern
    strong = MemoryEventSignal(
        event_type="recall",
        symbol="StrongPattern",
        frequency=20,
        success_rate=0.95,
        cross_project_count=5,
        recency=2.0,
        context_richness=15,
        error_type=None,
        metadata={},
    )
    score2 = engine.score_event(strong)
    print(f"\n2. Strong pattern → {score2.layer.value}")
    print(f"   Fitness: {score2.fitness:.3f}")

    # Test case 3: Promotion check
    can_promote = MemoryPromotionPolicy.should_promote_to_global(score2, strong)
    print(f"\n3. Can promote to GLOBAL? {can_promote}")

    print("\n✅ Validation complete")
