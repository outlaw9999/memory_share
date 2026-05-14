# Phase 10 — Reverse-Flow Test: intentional loop must be blocked
# Proves P3: ∀ loop, blocked(loop) = True

import os
from kit.runtime import PolicyGuard
from kit.runtime.policy_guard import _check_hook_depth
from kit.runtime.planner import ExecutionPlan, ExecutionStep
from kit.intent.schema import CanonicalIntent, IntentDomain, IntentAction
from kit.intent import normalize_git_event
from kit.intent.execution import ExecutionIntent, Mutability
from kit.vantage import EpistemicEngine, VerificationRequest, Verdict


def test_hook_depth_blocked():
    """KIT_HOOK_DEPTH > 5 must be blocked by PolicyGuard."""
    ci = CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT)
    plan = ExecutionPlan(intent=ci, steps=())
    payload = normalize_git_event("pre-commit")
    ex = ExecutionIntent.from_payload(payload)

    os.environ["KIT_HOOK_DEPTH"] = "7"
    assert _check_hook_depth(ex, plan) is not None
    del os.environ["KIT_HOOK_DEPTH"]

    os.environ["KIT_HOOK_DEPTH"] = "1"
    assert _check_hook_depth(ex, plan) is None
    del os.environ["KIT_HOOK_DEPTH"]
    print("[reverse-flow] hook depth > 5 blocked: OK")


def test_storm_prevention():
    """5 rapid identical intents must be blocked by PolicyGuard."""
    guard = PolicyGuard()
    ci = CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT)
    plan = ExecutionPlan(intent=ci, steps=())
    results = []
    for _ in range(5):
        ex = ExecutionIntent.from_payload(normalize_git_event("pre-commit"))
        results.append(guard.check(ex, plan))
    assert not results[-1].approved, "Storm should be blocked"
    print("[reverse-flow] storm prevention: OK")


def test_epistemic_depth_limit():
    """Execution depth >= 3 must be blocked by EpistemicEngine."""
    engine = EpistemicEngine()
    req = VerificationRequest()
    req.context.depth = 5
    result = engine.verify(req)
    assert result.verdict == Verdict.REJECTED, f"Expected REJECTED, got {result.verdict}"
    print("[reverse-flow] epistemic depth limit: OK")


def test_fingerprint_dedup():
    """Same request within 5s must be blocked by PolicyGuard fingerprint."""
    guard = PolicyGuard()
    ci = CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT)
    plan = ExecutionPlan(intent=ci, steps=())
    ex = ExecutionIntent.from_payload(normalize_git_event("pre-commit", commit_hash="dedup-test"))
    assert guard.check(ex, plan).approved, "First should pass"
    assert not guard.check(ex, plan).approved, "Duplicate should be blocked"
    print("[reverse-flow] fingerprint dedup: OK")


if __name__ == "__main__":
    test_hook_depth_blocked()
    test_storm_prevention()
    test_epistemic_depth_limit()
    test_fingerprint_dedup()
    print("ALL REVERSE-FLOW TESTS PASSED")
