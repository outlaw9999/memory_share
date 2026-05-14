# Phase 10 — Containment Test: inject hallucinated intent → must NOT reach Grounded domain
# Proves P2: ∀ hallucinated_intent, grounded(hallucinated_intent) = False

from tests.phase10.containment_harness import _validate_containment


def test_invalid_domain_rejected():
    r = _validate_containment("INTENT: INVALID:X", "Invalid")
    assert r.passed, r.detail
    assert r.blocked_at_layer == "normalizer"
    print(f"[containment] INVALID domain: blocked at {r.blocked_at_layer}")


def test_unregistered_intent_rejected():
    r = _validate_containment("INTENT: GRAPH:REBUILD", "No handler registered")
    assert r.passed, r.detail
    print(f"[containment] unregistered GRAPH:REBUILD: blocked at {r.blocked_at_layer}")


def test_garbage_input_rejected():
    r = _validate_containment("garbage input", "Unrecognized agent signal")
    assert r.passed, r.detail
    assert r.blocked_at_layer == "normalizer"
    print(f"[containment] garbage: blocked at {r.blocked_at_layer}")


def test_malformed_intent_rejected():
    r = _validate_containment("INTENT: ", "Unrecognized agent signal")
    assert r.passed, r.detail
    print(f"[containment] malformed: blocked at {r.blocked_at_layer}")


def test_long_signal_rejected():
    r = _validate_containment("INTENT: " + "A" * 200, "exceeds max length")
    assert r.passed, r.detail
    print(f"[containment] too long: blocked at {r.blocked_at_layer}")


if __name__ == "__main__":
    test_invalid_domain_rejected()
    test_unregistered_intent_rejected()
    test_garbage_input_rejected()
    test_malformed_intent_rejected()
    test_long_signal_rejected()
    print("ALL CONTAINMENT TESTS PASSED")
