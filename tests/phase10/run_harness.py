"""Run full Phase 10 containment harness and print report."""

from tests.phase10.containment_harness import run_full_harness

report = run_full_harness()
print("SUMMARY:", report.summary)
print()
for r in report.determinism:
    status = "PASS" if r.passed else "FAIL"
    print(f"  DET {r.input_label}: {status}  hashes={r.run_hashes}")
for r in report.containment:
    status = "PASS" if r.passed else "FAIL"
    print(f"  CON {r.injection[:40]}: {status}  blocked_at={r.blocked_at_layer}")
for r in report.reverse_flow:
    status = "PASS" if r.passed else "FAIL"
    print(f"  REV {r.scenario}: {status}  blocked_by={r.blocked_by}")
print()
print(f"ALL PASSED: {report.all_passed}")
