import time
from pathlib import Path

import pytest

from kit.cli.doctor import run_doctor
from kit.core.kit_cognitive_core import SAMBrain


@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "ranking_test.db"
    return SAMBrain(db_path)


def test_ranking_decay_and_saturation(brain):
    # 1. Old but high access fact
    fact1_id = brain.learn("node", "High frequency old fact", importance=1.0)
    for _ in range(10):
        brain.touch_fact(fact1_id)

    # 2. Fresh but low frequency fact
    _fact2_id = brain.learn("node", "Fresh new fact", importance=10.0)

    # Manually simulate decay for fact1
    with brain._get_connection() as conn:
        conn.execute("UPDATE observations SET created_at = julianday('now', '-30 days') WHERE id = ?", (fact1_id,))

    results = brain.recall(["node"])

    # Fresh fact with high importance should be top, even if old fact has high access (saturation curve)
    assert results[0].content == "Fresh new fact"


def test_namespace_boost(brain):
    # 1. Fact in shared namespace
    brain.learn("ui", "Shared UI fact", namespace="shared")

    # 2. Fact in agent specific namespace
    brain.learn("ui", "My private UI fact", namespace="agent_alice", agent_id="agent_alice")

    # Recall with agent_id
    results = brain.recall(["ui"], agent_id="agent_alice")

    # Agent's own namespace should be boosted
    assert results[0].content == "My private UI fact"


def test_scope_proximity_boost(brain, monkeypatch):
    brain.learn("auth", "Global auth rule", scope="")
    brain.learn("auth", "Scoped auth rule", scope="src/auth")

    (brain.root_path / "src" / "auth").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(brain.root_path / "src" / "auth")

    results = brain.recall(["auth"], here=True)

    assert results[0].content == "Scoped auth rule"


def test_search_namespace_boost(brain):
    brain.learn("cache", "Shared cache fact", namespace="shared")
    brain.learn("cache", "Private cache fact", namespace="agent_bob", agent_id="agent_bob")

    results = brain.search("cache", limit=5, agent_id="agent_bob")

    assert results[0].content == "Private cache fact"


def test_recall_assessment_detects_ambiguity(brain):
    brain.learn("cache", "Use Redis", importance=1.0, tag="decision")
    brain.learn("cache", "Use SQLite", importance=1.0, tag="decision")

    assessment = brain.recall_with_assessment(["cache"], limit=2)

    assert assessment.status == "AMBIGUOUS"
    assert assessment.confidence < brain.AMBIGUITY_THRESHOLD


def test_recall_assessment_detects_clear_winner(brain):
    brain.learn("auth", "JWT required", importance=1.0, tag="decision")
    brain.learn("auth", "maybe use session", importance=0.2, tag="note")

    assessment = brain.recall_with_assessment(["auth"], limit=2)

    assert assessment.status == "HIGH_CONFIDENCE"
    assert assessment.confidence >= brain.HIGH_CONFIDENCE_THRESHOLD
    assert assessment.memories[0].content == "JWT required"


def test_recall_assessment_returns_weak_signal_for_middle_band(brain):
    brain.learn("logging", "Prefer structured logs", importance=1.0, tag="decision")
    brain.learn("logging", "Plain text logs are acceptable", importance=0.7, tag="note")

    assessment = brain.recall_with_assessment(["logging"], limit=2)

    assert assessment.status == "WEAK_SIGNAL"
    assert brain.AMBIGUITY_THRESHOLD <= assessment.confidence < brain.HIGH_CONFIDENCE_THRESHOLD


def test_recall_combined_filters_bind_in_clause_order(brain, monkeypatch):
    brain.learn("auth", "Wrong symbol for same entity", scope="src/auth", symbol="wrong_symbol")
    brain.learn("auth", "Correct scoped symbol memory", scope="src/auth", symbol="validate_token")

    (brain.root_path / "src" / "auth").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(brain.root_path / "src" / "auth")

    results = brain.recall(["auth"], here=True, symbol="validate_token", limit=5)

    assert results
    assert results[0].content == "Correct scoped symbol memory"


def test_export_for_prompt_enforces_top_k_budget_and_omit_empty(brain):
    assert brain.export_for_prompt(["missing"]) == ""

    for idx in range(4):
        brain.learn(
            "prompt", f"Memory line {idx}\nextra detail that should not be rendered", importance=1.0 - (idx * 0.1)
        )

    exported = brain.export_for_prompt(["prompt"], limit=10, budget=80)
    lines = exported.splitlines()

    assert lines[0] == "<kit_memory>"
    assert lines[-1] == "</kit_memory>"
    assert len(lines[1:-1]) <= 3
    assert all("extra detail" not in line for line in lines[1:-1])
    assert len(exported) <= 80 + len("<kit_memory>\n</kit_memory>")


def test_doctor_reset_cloud_preserves_local_metrics(brain):
    with brain._get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_metrics (
                name TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO agent_metrics (name, data, updated_at) VALUES (?, ?, ?)",
            ("gemini", "{}", 0.0),
        )
        conn.execute(
            "INSERT INTO agent_metrics (name, data, updated_at) VALUES (?, ?, ?)",
            ("local", "{}", 0.0),
        )

    run_doctor(brain, check_agents=True, reset_cloud=True)

    with brain._get_connection() as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM agent_metrics ORDER BY name").fetchall()]

    assert names == ["local"]
