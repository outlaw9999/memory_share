#!/usr/bin/env python3
"""
Evolutionary Loop Tests v1.2.4

Tests the adaptive learning: Flow → Execute → Observe → Vantage → Adjust Flow
"""

import pytest
from kit.flow_vantage_bridge import FlowVantageBridge, FlowDecision, VantageSignal, get_bridge


import tempfile
from pathlib import Path

class TestEvolutionaryLoop:
    """Tests for the adaptive flow learning system."""

    def setup_method(self):
        """Set up test bridge with isolated DB."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_db = self.temp_dir / "test_flow_learning.db"
        self.bridge = FlowVantageBridge(db_path=self.test_db)

    def test_decision_recording(self):
        """Test recording of flow decisions."""
        decision = FlowDecision(
            signal_id="test_signal_001",
            route_taken="high_priority_route",
            priority=0.9,
            timestamp="2026-04-18T12:00:00Z",
            outcome="success"
        )

        self.bridge.record_decision(decision)

        # Verify recording
        insights = self.bridge.get_learning_insights()
        assert insights['total_decisions'] == 1

    def test_vantage_signal_integration(self):
        """Test Vantage analysis integration."""
        # Record decision first
        decision = FlowDecision(
            signal_id="test_signal_002",
            route_taken="standard_route",
            priority=0.6,
            timestamp="2026-04-18T12:01:00Z"
        )
        self.bridge.record_decision(decision)

        # Record Vantage analysis
        vantage = VantageSignal(
            decision_id=f"{decision.signal_id}_{decision.timestamp}",
            friction_detected=True,
            improvement_suggestions=["Increase priority threshold", "Consider alternative routing"],
            confidence_score=0.75,
            learning_weight=0.15
        )
        self.bridge.record_vantage_analysis(vantage)

        insights = self.bridge.get_learning_insights()
        assert insights['total_vantage_analyses'] == 1

    def test_adaptive_routing(self):
        """Test that routing adapts based on learning."""
        # Simulate multiple decisions with outcomes
        decisions = [
            ("signal_1", "route_a", 0.7, "success"),
            ("signal_2", "route_a", 0.7, "success"),
            ("signal_3", "route_b", 0.7, "failure"),
            ("signal_4", "route_a", 0.7, "success"),
        ]

        for signal_id, route, priority, outcome in decisions:
            decision = FlowDecision(
                signal_id=signal_id,
                route_taken=route,
                priority=priority,
                timestamp=f"2026-04-18T12:0{len(decisions)}:00Z",
                outcome=outcome
            )
            self.bridge.record_decision(decision)

        # Test adaptive routing
        signal = {'id': 'test_adaptive', 'importance': 0.7}
        base_routes = ['route_a', 'route_b', 'route_c']

        best_route = self.bridge.get_adaptive_route(signal, base_routes)

        # route_a should be preferred due to higher success rate
        assert best_route == 'route_a'

    def test_feedback_loop_simulation(self):
        """Test complete feedback loop simulation."""
        signal = {
            'id': 'feedback_test_signal',
            'importance': 0.8,
            'content': 'Test signal for feedback loop'
        }

        result = self.bridge.simulate_feedback_loop(signal)

        assert 'decision' in result
        assert 'vantage' in result
        assert 'insights' in result
        assert result['insights']['total_decisions'] >= 1
        assert result['insights']['total_vantage_analyses'] >= 1

    def test_learning_insights(self):
        """Test learning insights generation."""
        # Add some test data
        decision = FlowDecision(
            signal_id="insight_test",
            route_taken="test_route",
            priority=0.5,
            timestamp="2026-04-18T12:00:00Z",
            outcome="success"
        )
        self.bridge.record_decision(decision)

        insights = self.bridge.get_learning_insights()

        assert insights['total_decisions'] == 1
        assert 'route_performance' in insights
        assert len(insights['route_performance']) > 0

    def test_weight_evolution(self):
        """Test that routing weights evolve over time."""
        # Initial state
        initial_weights = self.bridge.get_learning_insights()['route_performance']

        # Add successful decisions
        for i in range(5):
            decision = FlowDecision(
                signal_id=f"evolution_test_{i}",
                route_taken="evolving_route",
                priority=0.6,
                timestamp=f"2026-04-18T12:0{i}:00Z",
                outcome="success"
            )
            self.bridge.record_decision(decision)

        # Add Vantage feedback
        for i in range(3):
            vantage = VantageSignal(
                decision_id=f"evolution_test_{i}_2026-04-18T12:0{i}:00Z",
                friction_detected=False,
                improvement_suggestions=["Good decision"],
                confidence_score=0.8,
                learning_weight=0.1
            )
            self.bridge.record_vantage_analysis(vantage)

        # Check evolved weights
        evolved_weights = self.bridge.get_learning_insights()['route_performance']

        # Find evolving_route performance
        evolving_route = next((r for r in evolved_weights if r['route'] == 'evolving_route'), None)
        assert evolving_route is not None
        assert evolving_route['success_rate'] > 0.5  # Should be 1.0
        assert evolving_route['total_decisions'] == 5

    def test_bridge_singleton(self):
        """Test that get_bridge returns singleton instance."""
        bridge1 = get_bridge()
        bridge2 = get_bridge()

        assert bridge1 is bridge2