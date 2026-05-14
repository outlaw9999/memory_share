"""
RegressionCorpus - Given-When-Then test scenarios for cognitive flows.

v1.2.5: Defines test scenarios for validating:
- Flow regression (7-state machine transitions)
- Recall → Think → Learn pipeline
- Decision tier outputs
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class GivenWhenThen:
    """A test scenario following Given-When-Then pattern."""

    id: str
    description: str
    given: dict
    when: dict
    then: dict
    tags: list[str] = field(default_factory=list)


@dataclass
class RegressionScenario:
    """A complete regression scenario."""

    id: str
    name: str
    description: str
    steps: list[GivenWhenThen]
    expected_state: dict = field(default_factory=dict)
    severity: str = "critical"  # critical, major, minor
    deterministic: bool = True


def load_default_corpus() -> RegressionCorpus:
    """Load default corpus with flow scenarios."""
    corpus = RegressionCorpus()
    for scenario in DEFAULT_FLOW_SCENARIOS:
        corpus.scenarios[scenario.id] = scenario
    return corpus


class RegressionCorpus:
    """
    Collection of regression scenarios for cognitive flows.

    Loads scenarios from JSON files and provides test execution.
    """

    def __init__(self, corpus_dir: Path | None = None, load_defaults: bool = True):
        self.corpus_dir = corpus_dir
        self.scenarios: dict[str, RegressionScenario] = {}
        if load_defaults:
            for scenario in DEFAULT_FLOW_SCENARIOS:
                self.scenarios[scenario.id] = scenario
        if corpus_dir and corpus_dir.exists():
            self._load_from_dir(corpus_dir)

    def _load_from_dir(self, corpus_dir: Path):
        """Load scenarios from directory."""
        for json_file in corpus_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                for scenario_data in data.get("scenarios", []):
                    scenario = self._parse_scenario(scenario_data)
                    self.scenarios[scenario.id] = scenario
            except Exception as e:
                print(f"Warning: Failed to load {json_file}: {e}")

    def _parse_scenario(self, data: dict) -> RegressionScenario:
        """Parse scenario from dict."""
        steps = [
            GivenWhenThen(
                id=s["id"],
                description=s["description"],
                given=s["given"],
                when=s["when"],
                then=s["then"],
                tags=s.get("tags", []),
            )
            for s in data.get("steps", [])
        ]

        return RegressionScenario(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            expected_state=data.get("expected_state", {}),
            severity=data.get("severity", "critical"),
            deterministic=data.get("deterministic", True),
        )

    def get_scenario(self, id: str) -> RegressionScenario | None:
        """Get scenario by ID."""
        return self.scenarios.get(id)

    def list_scenarios(
        self,
        tags: list[str] | None = None,
        severity: str | None = None,
    ) -> list[RegressionScenario]:
        """List scenarios filtered by tags or severity."""
        results = list(self.scenarios.values())

        if tags:
            results = [s for s in results if s.steps and any(t in s.steps[0].tags for t in tags)]

        if severity:
            results = [s for s in results if s.severity == severity]

        return results

    def run_scenario(
        self,
        scenario: RegressionScenario,
        executor: Callable[[GivenWhenThen], Any],
    ) -> tuple[bool, dict]:
        """
        Execute scenario with given executor.

        Returns (success, results).
        """
        results = {
            "scenario_id": scenario.id,
            "steps_executed": [],
            "success": True,
            "errors": [],
        }

        for step in scenario.steps:
            try:
                result = executor(step)
                results["steps_executed"].append(
                    {
                        "step_id": step.id,
                        "result": result,
                    }
                )
            except Exception as e:
                results["success"] = False
                results["errors"].append(
                    {
                        "step_id": step.id,
                        "error": str(e),
                    }
                )

        return results["success"], results


DEFAULT_FLOW_SCENARIOS = [
    RegressionScenario(
        id="flow_001_empty_brain",
        name="Empty Brain Recall",
        description="Test recall on empty brain returns empty list",
        steps=[
            GivenWhenThen(
                id="g1",
                description="Empty brain",
                given={
                    "brain_state": "empty",
                    "observations": [],
                },
                when={
                    "action": "recall",
                    "signals": ["test:signal"],
                },
                then={
                    "expected": "empty_result",
                    "count": 0,
                },
                tags=["recall", "empty"],
            ),
        ],
        expected_state={"observations": 0},
        severity="critical",
    ),
    RegressionScenario(
        id="flow_002_single_learn",
        name="Single Learn",
        description="Test learn creates observation",
        steps=[
            GivenWhenThen(
                id="g1",
                description="Empty brain",
                given={"brain_state": "empty"},
                when={
                    "action": "learn",
                    "uid": "test:fact1",
                    "content": "A test fact",
                    "tag": "decision",
                },
                then={
                    "expected": "observation_created",
                    "count": 1,
                },
                tags=["learn", "create"],
            ),
        ],
        expected_state={"observations": 1},
        severity="critical",
    ),
    RegressionScenario(
        id="flow_003_recall_after_learn",
        name="Recall After Learn",
        description="Test recall returns previously learned fact",
        steps=[
            GivenWhenThen(
                id="g1",
                description="Brain with fact",
                given={
                    "observations": [{"uid": "test:fact1", "content": "A test fact"}],
                },
                when={
                    "action": "recall",
                    "signals": ["test"],
                },
                then={
                    "expected": "result_found",
                    "count": 1,
                    "content_contains": "test fact",
                },
                tags=["recall", "retrieve"],
            ),
        ],
        expected_state={"observations": 1},
        severity="critical",
    ),
    RegressionScenario(
        id="flow_004_conflict_resolution",
        name="Conflict Resolution",
        description="Test invariant wins over decision",
        steps=[
            GivenWhenThen(
                id="g1",
                description="Conflicting memories",
                given={
                    "observations": [
                        {"uid": "inv:rule", "tag": "invariant", "content": "Rule 1"},
                        {"uid": "dec:override", "tag": "decision", "content": "Override"},
                    ],
                },
                when={
                    "action": "recall",
                    "signals": ["rule"],
                },
                then={
                    "expected": "invariant_wins",
                    "winner_tag": "invariant",
                },
                tags=["conflict", "resolution"],
            ),
        ],
        expected_state={"observations": 2},
        severity="critical",
    ),
    RegressionScenario(
        id="flow_005_duplicate_detection",
        name="Duplicate Detection",
        description="Test duplicate UID is rejected",
        steps=[
            GivenWhenThen(
                id="g1",
                description="Existing UID",
                given={
                    "observations": [
                        {"uid": "test:duplicate", "content": "First"},
                    ],
                },
                when={
                    "action": "learn",
                    "uid": "test:duplicate",
                    "content": "Second",
                },
                then={
                    "expected": "duplicate_rejected",
                    "error": "UNIQUE constraint",
                },
                tags=["learn", "duplicate"],
            ),
        ],
        expected_state={"observations": 1},
        severity="critical",
    ),
]


def create_default_corpus() -> RegressionCorpus:
    """Create corpus with default flow scenarios."""
    corpus = RegressionCorpus()
    for scenario in DEFAULT_FLOW_SCENARIOS:
        corpus.scenarios[scenario.id] = scenario
    return corpus


def load_corpus_from_file(path: Path) -> RegressionCorpus:
    """Load corpus from JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios = []
    for scenario_data in data.get("scenarios", []):
        steps = [
            GivenWhenThen(
                id=s["id"],
                description=s["description"],
                given=s["given"],
                when=s["when"],
                then=s["then"],
                tags=s.get("tags", []),
            )
            for s in scenario_data.get("steps", [])
        ]
        scenarios.append(
            RegressionScenario(
                id=scenario_data["id"],
                name=scenario_data["name"],
                description=scenario_data.get("description", ""),
                steps=steps,
                expected_state=scenario_data.get("expected_state", {}),
                severity=scenario_data.get("severity", "critical"),
            )
        )

    corpus = RegressionCorpus()
    for s in scenarios:
        corpus.scenarios[s.id] = s
    return corpus
