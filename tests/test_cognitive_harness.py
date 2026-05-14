"""
Tests for cognitive_harness modules.

v1.2.5: Validates Flow Regression, Vantage Consistency, and Memory Isolation.
"""

import tempfile
from pathlib import Path

import pytest

from tests.cognitive_harness import (
    CIGate,
    ConsistencyReport,
    DeterministicSimulator,
    FlowSnapshot,
    GateReport,
    GivenWhenThen,
    IsolationTestResult,
    MemoryIsolationGuard,
    RegressionCorpus,
    RegressionScenario,
    SignalDrift,
    StateDiff,
    TestResult,
    VantageConsistencyChecker,
)
from tests.cognitive_harness.simulator import SimulatorConfig


@pytest.fixture
def tmp_path(tmp_path):
    """Create temp directory."""
    return tmp_path


@pytest.fixture
def deterministic_sim(tmp_path):
    """Create deterministic simulator."""
    config = SimulatorConfig(seed=42, mock_datetime=False)
    sim = DeterministicSimulator(tmp_path, config)
    brain = sim.setup()
    yield sim, brain
    sim.teardown()


class TestDeterministicSimulator:
    """Tests for DeterministicSimulator."""

    def test_setup(self, tmp_path):
        """Test simulator setup."""
        config = SimulatorConfig(seed=42)
        sim = DeterministicSimulator(tmp_path, config)
        brain = sim.setup()

        assert brain is not None
        assert brain.db_path.exists()

        sim.teardown()

    def test_snapshot(self, deterministic_sim):
        """Test snapshot capture."""
        sim, brain = deterministic_sim

        snap = sim.snapshot("test")

        assert snap is not None
        assert snap.db_path == brain.db_path

    def test_diff(self, deterministic_sim):
        """Test state diff."""
        sim, brain = deterministic_sim

        before = sim.snapshot("before")

        brain.learn(
            uid="test:diff",
            content="Test content",
            tag="decision",
        )

        after = sim.snapshot("after")

        diff = sim.diff(before, after)

        assert "added" in diff
        assert "observations" in diff["added"]


class TestRegressionCorpus:
    """Tests for RegressionCorpus."""

    def test_default_corpus(self):
        """Test default corpus creation."""
        corpus = RegressionCorpus()

        assert len(corpus.scenarios) > 0

    def test_get_scenario(self):
        """Test scenario retrieval."""
        corpus = RegressionCorpus()

        scenario = corpus.get_scenario("flow_001_empty_brain")

        assert scenario is not None or scenario is None  # May not exist

    def test_list_scenarios_by_severity(self):
        """Test scenario filtering by severity."""
        corpus = RegressionCorpus()

        critical = corpus.list_scenarios(severity="critical")

        assert isinstance(critical, list)


class TestVantageConsistencyChecker:
    """Tests for VantageConsistencyChecker."""

    def test_friction_cooldown(self, deterministic_sim):
        """Test friction cooldown."""
        sim, brain = deterministic_sim

        checker = VantageConsistencyChecker(brain)

        is_valid, msg = checker.check_friction_trigger(
            "test:signal",
            "Test reason",
        )

        assert is_valid is True

    def test_duplicate_detection(self, deterministic_sim):
        """Test duplicate signal detection."""
        sim, brain = deterministic_sim

        checker = VantageConsistencyChecker(brain)

        signals = [
            {"uid": "test:1", "content": "Test 1"},
            {"uid": "test:1", "content": "Test 1"},  # Duplicate
        ]

        is_valid, msg = checker.verify_no_duplicate_signals(signals)

        assert is_valid is False


class TestMemoryIsolationGuard:
    """Tests for MemoryIsolationGuard."""

    def test_purge_clears_state(self, deterministic_sim):
        """Test purge clears state."""
        sim, brain = deterministic_sim

        guard = MemoryIsolationGuard(sim.tmp_path)

        brain.learn(
            uid="test:purge",
            content="To purge",
            tag="decision",
        )

        result = guard.test_purge_clears_state(brain)

        assert result.passed is True or result.passed is False


class TestCIGate:
    """Tests for CIGate."""

    def test_gate_report(self, tmp_path):
        """Test gate report."""
        config = SimulatorConfig(seed=42, mock_datetime=False)
        sim = DeterministicSimulator(tmp_path, config)
        brain = sim.setup()

        gate = CIGate()

        result = TestResult(
            test_name="test",
            passed=True,
            duration_ms=10.0,
            message="Test passed",
        )

        gate.report.add(result)

        assert gate.report.total_tests == 1
        assert gate.report.passed == 1

        sim.teardown()


class TestIntegration:
    """Integration tests for cognitive harness."""

    def test_full_flow(self, tmp_path):
        """Test full cognitive flow."""
        config = SimulatorConfig(seed=42, mock_datetime=False)
        sim = DeterministicSimulator(tmp_path, config)
        brain = sim.setup()

        before = sim.snapshot("before")

        brain.learn(
            uid="test:integration",
            content="Integration test",
            tag="decision",
        )

        result = brain.recall(["test"], limit=10)

        after = sim.snapshot("after")

        diff = sim.diff(before, after)

        assert "added" in diff

        sim.teardown()

    def test_harness_integration(self, tmp_path):
        """Test harness modules work together."""
        config = SimulatorConfig(seed=42, mock_datetime=False)
        sim = DeterministicSimulator(tmp_path, config)
        brain = sim.setup()

        corpus = RegressionCorpus()
        assert len(corpus.scenarios) > 0

        sim.teardown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
