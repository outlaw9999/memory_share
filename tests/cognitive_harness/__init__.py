"""
Cognitive TDD Harness v1.2.5

A test framework for validating KIT's cognitive runtime through:
- Flow Regression Gate
- Vantage Consistency Loop
- Memory Isolation & Sealing Invariance

Architecture:
- DeterministicSimulator: Mock time/uuid/vantage for reproducibility
- StateDiff: Snapshot comparison for state verification
- RegressionCorpus: Given-When-Then test scenarios
- VantageConsistencyChecker: Signal drift detection
- MemoryIsolationGuard: Scope boundary tests
- CIGate: CI/CD integration
"""

from tests.cognitive_harness.consistency import ConsistencyReport, SignalDrift, VantageConsistencyChecker
from tests.cognitive_harness.corpus import GivenWhenThen, RegressionCorpus, RegressionScenario
from tests.cognitive_harness.gate import CIGate, GateReport, TestResult
from tests.cognitive_harness.isolation import IsolationTestResult, MemoryIsolationGuard
from tests.cognitive_harness.simulator import DeterministicSimulator, FlowSnapshot
from tests.cognitive_harness.state_diff import StateDiff

__all__ = [
    "DeterministicSimulator",
    "FlowSnapshot",
    "StateDiff",
    "RegressionCorpus",
    "GivenWhenThen",
    "RegressionScenario",
    "VantageConsistencyChecker",
    "SignalDrift",
    "ConsistencyReport",
    "MemoryIsolationGuard",
    "IsolationTestResult",
    "CIGate",
    "GateReport",
    "TestResult",
]
