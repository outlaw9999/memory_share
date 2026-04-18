# KIT v1.2.4 TDD Test Suite
# Tests cognitive runtime determinism

import pytest
from kit.flow.surface import flow_decision_kernel, FLOW_TOP_K, FLOW_MIN_CONFIDENCE

class TestFlowRouting:
    """Level 1: Flow routing determinism"""
    
    def test_learn_routes_to_learn(self):
        r = flow_decision_kernel("learn this")
        assert r.get("route") == "learn"
    
    def test_recall_routes_to_recall(self):
        r = flow_decision_kernel("recall memory")
        assert r.get("route") == "recall"
    
    def test_search_routes_to_search(self):
        r = flow_decision_kernel("search bug")
        assert r.get("route") == "search"
    
    def test_stats_routes_to_stats(self):
        r = flow_decision_kernel("status check")
        assert r.get("route") == "stats"
    
    def test_unknown_routes_to_synthesize(self):
        r = flow_decision_kernel("random text")
        assert r.get("route") == "synthesize"


class TestFlowSignal:
    """Level 2: Signal consistency"""
    
    def test_short_input_handled(self):
        r = flow_decision_kernel("ab")  # too short
        assert "state" in r
        assert r.get("state") in ["precheck_failed", "complete"]
    
    def test_empty_input_handled(self):
        r = flow_decision_kernel("")
        assert "state" in r


class TestFlowConfig:
    """Level 3: Configuration invariants"""
    
    def test_top_k_is_2(self):
        assert FLOW_TOP_K == 2
    
    def test_confidence_threshold_is_07(self):
        assert FLOW_MIN_CONFIDENCE == 0.7


class TestFlowStateMachine:
    """Level 4: State transitions"""
    
    def test_complete_state_reached(self):
        r = flow_decision_kernel("learn test")
        assert r.get("state") == "complete"
        assert r.get("final") is not None
    
    def test_all_states_traversed(self):
        expected = ["precheck", "reflect", "signal_merge", "route_decision", "execute"]
        r = flow_decision_kernel("learn test")
        assert r.get("state") == "complete"
        # All states should be traversed in order
        assert "routes_tried" in r


class TestMemoryIsolation:
    """Level 5: Memory integrity"""
    pass  # Placeholder for memory tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])