"""
CIGate - CI/CD integration for cognitive TDD.

v1.2.5: Provides command-line interface for running:
- Flow Regression Gate
- Vantage Consistency Loop
- Memory Isolation & Sealing Tests

Usage:
    python -m tests.cognitive_harness.gate run --deterministic
    python -m tests.cognitive_harness.gate verify --corpus
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tests.cognitive_harness.consistency import (
    VantageConsistencyChecker,
    run_friction_stress_test,
)
from tests.cognitive_harness.corpus import (
    RegressionCorpus,
    create_default_corpus,
    load_corpus_from_file,
)
from tests.cognitive_harness.isolation import (
    MemoryIsolationGuard,
    run_isolation_suite,
    test_concurrent_isolation,
)
from tests.cognitive_harness.simulator import (
    DeterministicSimulator,
    SimulatorConfig,
)


@dataclass
class TestResult:
    """Result of a single test."""

    test_name: str
    passed: bool
    duration_ms: float
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class GateReport:
    """Report from CI Gate execution."""

    timestamp: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    results: list[TestResult] = field(default_factory=list)
    failed_tests: list = field(default_factory=list)

    def add(self, result: TestResult):
        self.results.append(result)
        self.total_tests += 1

        if result.passed:
            self.passed += 1
        else:
            self.failed += 1
            self.failed_tests.append(result.test_name)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": f"{(self.passed / self.total_tests * 100):.1f}%" if self.total_tests > 0 else "N/A",
            "failed_tests": self.failed_tests,
            "results": [
                {
                    "test": r.test_name,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "message": r.message,
                }
                for r in self.results
            ],
        }


class CIGate:
    """
    CI Gate for cognitive TDD.

    Run tests deterministically and fail on any regression.
    """

    def __init__(self, output_path: Path | None = None):
        self.output_path = output_path
        self.report = GateReport(timestamp=datetime.now().isoformat())

    def run_flow_regression(
        self,
        brain,
        corpus: RegressionCorpus | None = None,
    ) -> GateReport:
        """Run flow regression tests."""
        if corpus is None:
            corpus = create_default_corpus()

        print(f"[CIGate] Running {len(corpus.scenarios)} flow regression scenarios...")

        for scenario in corpus.scenarios.values():
            start = time.time()

            try:
                passed = self._execute_scenario(brain, scenario)
                duration = (time.time() - start) * 1000

                result = TestResult(
                    test_name=scenario.id,
                    passed=passed,
                    duration_ms=duration,
                    message=f"{scenario.name}: {'PASS' if passed else 'FAIL'}",
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                result = TestResult(
                    test_name=scenario.id,
                    passed=False,
                    duration_ms=duration,
                    message=f"Exception: {str(e)}",
                )

            self.report.add(result)
            print(f"  {result.test_name}: {result.message} ({result.duration_ms:.1f}ms)")

        return self.report

    def _execute_scenario(self, brain, scenario) -> bool:
        """Execute a single scenario."""
        for step in scenario.steps:
            action = step.when.get("action")

            if action == "learn":
                brain.learn(
                    uid=step.when.get("uid", ""),
                    content=step.when.get("content", ""),
                    tag=step.when.get("tag", "decision"),
                )
            elif action == "recall":
                signals = step.when.get("signals", [])
                results = brain.recall(signals, limit=10)
                expected = step.then.get("count", 0)

                if expected > 0 and len(results) == 0:
                    return False
                if expected == 0 and len(results) > 0:
                    return False

        return True

    def run_consistency_check(self, brain) -> GateReport:
        """Run vantage consistency checks."""
        print("[CIGate] Running consistency checks...")

        checker = VantageConsistencyChecker(brain)

        start = time.time()
        friction_results = run_friction_stress_test(brain, num_triggers=50)
        duration = (time.time() - start) * 1000

        spam_rate = friction_results["spam_detected"] / friction_results["total_triggers"]

        result = TestResult(
            test_name="friction_cooldown",
            passed=spam_rate > 0.5,
            duration_ms=duration,
            message=f"Spam rate: {spam_rate:.1%}",
            details=friction_results,
        )
        self.report.add(result)

        print(f"  friction_cooldown: {result.message}")

        return self.report

    def run_isolation_tests(self, tmp_path: Path) -> GateReport:
        """Run memory isolation tests."""
        print("[CIGate] Running isolation tests...")

        start = time.time()
        isolation_results = run_isolation_suite(tmp_path)
        duration = (time.time() - start) * 1000

        result = TestResult(
            test_name="isolation_suite",
            passed=isolation_results["failed"] == 0,
            duration_ms=duration,
            message=f"{isolation_results['passed']}/{isolation_results['tests']} passed",
            details=isolation_results,
        )
        self.report.add(result)

        print(f"  isolation_suite: {result.message}")

        start = time.time()
        concurrent_result = test_concurrent_isolation()
        duration = (time.time() - start) * 1000

        self.report.add(
            TestResult(
                test_name="concurrent_isolation",
                passed=concurrent_result.passed,
                duration_ms=duration,
                message=concurrent_result.message,
            )
        )

        print(f"  concurrent_isolation: {concurrent_result.message}")

        return self.report

    def run_deterministic_check(
        self,
        brain,
        num_runs: int = 3,
    ) -> GateReport:
        """Check determinism: same input = same output."""
        print(f"[CIGate] Running determinism check ({num_runs} runs)...")

        hashes = []

        for i in range(num_runs):
            brain.learn(
                uid=f"det:test:{i}",
                content=f"Deterministic fact {i}",
                tag="decision",
            )

            with brain.get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) FROM observations").fetchone()
                hashes.append(row[0] if row else 0)

        is_deterministic = len(set(hashes)) == 1

        result = TestResult(
            test_name="determinism",
            passed=is_deterministic,
            duration_ms=0,
            message=f"Hashes: {hashes}",
        )
        self.report.add(result)

        print(f"  determinism: {result.message}")

        return self.report

    def run_all(
        self,
        brain,
        tmp_path: Path,
        corpus: RegressionCorpus | None = None,
    ) -> GateReport:
        """Run all CI gates."""
        print("[CIGate] Running full test suite...")
        print("=" * 50)

        self.run_flow_regression(brain, corpus)
        self.run_consistency_check(brain)
        self.run_isolation_tests(tmp_path)
        self.run_deterministic_check(brain)

        print("=" * 50)
        print(f"Results: {self.report.passed}/{self.report.total_tests} passed")
        print(f"Failed: {self.report.failed_tests}")

        if self.output_path:
            output = self.report.to_dict()
            self.output_path.write_text(
                json.dumps(output, indent=2),
                encoding="utf-8",
            )
            print(f"Report written to: {self.output_path}")

        return self.report


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Cognitive TDD CI Gate")
    parser.add_argument("command", choices=["run", "verify"], help="Command")
    parser.add_argument("--deterministic", action="store_true", help="Run deterministic mode")
    parser.add_argument("--corpus", type=Path, help="Corpus file path")
    parser.add_argument("--output", type=Path, help="Output report path")
    parser.add_argument("--tmp-path", type=Path, help="Temp directory")

    args = parser.parse_args()

    import tempfile

    if args.tmp_path:
        tmp_path = args.tmp_path
    else:
        tmp_path = Path(tempfile.mkdtemp())

    tmp_path.mkdir(parents=True, exist_ok=True)

    config = SimulatorConfig()
    if args.deterministic:
        config.mock_datetime = True
        config.mock_uuid = True
        config.seed = 42

    sim = DeterministicSimulator(tmp_path, config)
    brain = sim.setup()

    corpus = None
    if args.corpus:
        corpus = load_corpus_from_file(args.corpus)

    gate = CIGate(output_path=args.output)

    if args.command == "run":
        gate.run_all(brain, tmp_path, corpus)
    elif args.command == "verify":
        gate.run_flow_regression(brain, corpus)

    success = gate.report.failed == 0

    sim.teardown()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
