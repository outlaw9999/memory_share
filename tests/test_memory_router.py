# tests/test_memory_router.py
# v1.2.5 — TDD for Memory Router (Gatekeeper)

import os
import sys
import tempfile
from pathlib import Path

# Setup path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit.core.memory_router import (
    MemoryRouter,
    MemoryRouterFactory,
    MemoryTier,
    MemoryTierRules,
    MemoryWriteRequest,
    WriteDecision,
    WriteSource,
)


def test_validate_confidence_out_of_range():
    """Confidence must be [0.0, 1.0]."""
    req = MemoryWriteRequest(
        source=WriteSource.TRAINER,
        key="test",
        content="content",
        confidence=1.5,
        metadata={},
    )
    is_valid, reason = MemoryTierRules.validate_request(req)
    assert not is_valid
    print("✓ Reject confidence > 1.0")


def test_validate_below_threshold():
    """Confidence below LOCAL threshold → rejected."""
    req = MemoryWriteRequest(
        source=WriteSource.TRAINER,
        key="test",
        content="content",
        confidence=0.2,
        metadata={},
    )
    is_valid, reason = MemoryTierRules.validate_request(req)
    assert not is_valid
    print("✓ Reject confidence < 0.30")


def test_route_to_local():
    """Confidence 0.30-0.59 → LOCAL tier."""
    req = MemoryWriteRequest(
        source=WriteSource.TRAINER,
        key="test",
        content="content",
        confidence=0.45,
        metadata={},
    )
    tier = MemoryTierRules.route_to_tier(req)
    assert tier == MemoryTier.LOCAL
    print("✓ Route confidence 0.45 → LOCAL")


def test_route_to_global():
    """Confidence 0.60-0.84 → GLOBAL tier."""
    req = MemoryWriteRequest(
        source=WriteSource.TRAINER,
        key="test",
        content="content",
        confidence=0.75,
        metadata={},
    )
    tier = MemoryTierRules.route_to_tier(req)
    assert tier == MemoryTier.GLOBAL
    print("✓ Route confidence 0.75 → GLOBAL")


def test_route_to_frozen():
    """Confidence >= 0.95 → FROZEN tier."""
    req = MemoryWriteRequest(
        source=WriteSource.TRAINER,
        key="test",
        content="content",
        confidence=0.96,
        metadata={},
    )
    tier = MemoryTierRules.route_to_tier(req)
    assert tier == MemoryTier.FROZEN
    print("✓ Route confidence 0.96 → FROZEN")


def test_accept_valid_memory():
    """Valid request → ACCEPTED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KIT_GLOBAL_HOME"] = str(Path(tmpdir) / "global")
        project_root = Path(tmpdir)
        router = MemoryRouterFactory.create(project_root)

        req = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="pattern:test",
            content={"data": "test"},
            confidence=0.75,
            metadata={"frequency": 5},
        )
        decision = router.route_write(req)

        assert decision.decision == WriteDecision.ACCEPTED
        assert decision.assigned_tier == MemoryTier.GLOBAL

        # v1.2.5: Release handles
        router.close()

        print("✓ Accept valid memory (0.75 confidence)")


def test_reject_low_confidence():
    """Low confidence → REJECTED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KIT_GLOBAL_HOME"] = str(Path(tmpdir) / "global")
        project_root = Path(tmpdir)
        router = MemoryRouterFactory.create(project_root)

        req = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="pattern:weak",
            content={"data": "weak"},
            confidence=0.15,
            metadata={},
        )
        decision = router.route_write(req)

        assert decision.decision == WriteDecision.REJECTED

        # v1.2.5: Release handles
        router.close()

        print("✓ Reject low confidence (0.15)")


def test_statistics():
    """Router tracks statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KIT_GLOBAL_HOME"] = str(Path(tmpdir) / "global")
        project_root = Path(tmpdir)
        router = MemoryRouterFactory.create(project_root)

        # Accept one
        req1 = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="test1",
            content="c1",
            confidence=0.75,
            metadata={},
        )
        router.route_write(req1)

        # Reject one
        req2 = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="test2",
            content="c2",
            confidence=0.15,
            metadata={},
        )
        router.route_write(req2)

        stats = router.stats()

        assert stats["total_requests"] == 2
        assert stats["accepted"] == 1
        assert stats["rejected"] == 1

        # v1.2.5: Release handles
        router.close()

        print("✓ Statistics: 2 requests, 1 accepted, 1 rejected")


def test_deterministic_routing():
    """INVARIANT: Same confidence → same tier (always)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KIT_GLOBAL_HOME"] = str(Path(tmpdir) / "global")
        project_root = Path(tmpdir)
        router = MemoryRouterFactory.create(project_root)

        confidence = 0.72

        for i in range(3):
            req = MemoryWriteRequest(
                source=WriteSource.TRAINER,
                key=f"test_{i}",
                content="content",
                confidence=confidence,
                metadata={},
            )
            decision = router.route_write(req)
            assert decision.assigned_tier == MemoryTier.GLOBAL

        # v1.2.5: Release handles
        router.close()

        print("✓ INVARIANT: Deterministic routing (0.72 → GLOBAL always)")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧠 KIT v1.2.5 Memory Router - TDD Validation")
    print("=" * 70 + "\n")

    tests = [
        test_validate_confidence_out_of_range,
        test_validate_below_threshold,
        test_route_to_local,
        test_route_to_global,
        test_route_to_frozen,
        test_accept_valid_memory,
        test_reject_low_confidence,
        test_statistics,
        test_deterministic_routing,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: EXCEPTION: {e}")
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")
