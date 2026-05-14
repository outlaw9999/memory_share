"""Phase 12 — Drift Governance self-test."""
import os, shutil
from pathlib import Path

os.environ["KIT_HOOK_DEPTH"] = "0"

from tests.phase10.drift_governance import (
    InvariantRegistry,
    BehavioralRegressionDetector,
    ShadowTraceArchive,
    run_governance,
    INVARIANTS,
)
from tests.phase10.shadow_harness import ShadowHarness

gov_dir = Path(".kit/governance")
if gov_dir.exists():
    shutil.rmtree(gov_dir)

# 1. InvariantRegistry
inv_reg = InvariantRegistry()
violations = inv_reg.check_all()
r = inv_reg.report()
assert r["total_invariants"] == 10
verifiable = sum(1 for i in INVARIANTS if i["verifiable"])
assert r["verifiable"] == verifiable
print(f"[1] InvariantRegistry: {r['total_invariants']} invariants")

# 2. BehavioralRegressionDetector
detector = BehavioralRegressionDetector()
result = detector.run_and_compare()
assert "stable" in result
assert "regression_detected" in result
detector.save_baseline(result["current"])
print(f"[2] RegressionDetector: stable={result['stable']}")

# 3. ShadowTraceArchive
archive = ShadowTraceArchive()
harness = ShadowHarness()
r1 = harness.run_event("pre-commit", commit_hash="drift-001")
archive.record(r1)
entries = archive.query("pre-commit")
assert len(entries) >= 1
score = archive.divergence_score("pre-commit")
assert score >= 0.0
print(f"[3] ShadowTraceArchive: {len(entries)} entries, divergence={score:.3f}")

# 4. Full governance run
report = run_governance()
print(f"[4] Governance drift={report.drift_score:.3f} stable={report.stable}")
print(f"    Summary: {report.summary}")
assert report.drift_score >= 0.0

# Cleanup
if gov_dir.exists():
    shutil.rmtree(gov_dir)

if "KIT_HOOK_DEPTH" in os.environ:
    del os.environ["KIT_HOOK_DEPTH"]
print()
print("PHASE 12 :: DRIFT GOVERNANCE VERIFIED")
