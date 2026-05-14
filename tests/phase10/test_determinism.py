# Phase 10 — Determinism Test: same input → same trace hash
# Proves P1: ∀ event, execute_n(event) = execute_m(event) ⇒ hash_m = hash_n

from tests.phase10.containment_harness import check_determinism, _build_registry
from kit.intent.normalizer import normalize_agent_signal, normalize_git_event


def test_determinism_learn():
    def make():
        return normalize_agent_signal("INTENT: MEMORY:LEARN"), _build_registry()
    result = check_determinism(make, runs=3)
    assert result.deterministic, result.failure_detail
    print(f"[determinism] MEMORY:LEARN — {result.run_hashes}")


def test_determinism_precommit():
    def make():
        return normalize_git_event("pre-commit"), _build_registry()
    result = check_determinism(make, runs=3)
    assert result.deterministic, result.failure_detail
    print(f"[determinism] PRE_COMMIT — {result.run_hashes}")


def test_determinism_recall():
    def make():
        return normalize_agent_signal("INTENT: MEMORY:RECALL"), _build_registry()
    result = check_determinism(make, runs=3)
    assert result.deterministic, result.failure_detail
    print(f"[determinism] MEMORY:RECALL — {result.run_hashes}")


if __name__ == "__main__":
    test_determinism_learn()
    test_determinism_precommit()
    test_determinism_recall()
    print("ALL DETERMINISM TESTS PASSED")
