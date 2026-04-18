#!/usr/bin/env python3
"""
Unified Validation System v1.2.4

Single source of truth for all validation: CI/CD + TDD + Flow Runtime

This system collapses all fragmented validation into one coherent framework.
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from kit.api import resolve_paths


@dataclass
class ValidationResult:
    """Result of a validation component."""
    component: str
    status: str  # 'PASS', 'FAIL', 'SKIP'
    duration: float
    details: Dict[str, Any]
    timestamp: str


@dataclass
class SystemValidationReport:
    """Complete validation report."""
    overall_status: str
    components: List[ValidationResult]
    summary: Dict[str, Any]
    generated_at: str


class UnifiedValidator:
    """Unified validation system for v1.2.4."""

    def __init__(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.results: List[ValidationResult] = []

    def run_command(self, cmd: str, cwd: Optional[Path] = None) -> tuple[bool, str, str]:
        """Run a command and return success status, stdout, stderr."""
        if cwd is None:
            cwd = self.repo_root

        # v1.2.4-ISOLATION: Enforce deterministic environment for all validation steps
        env = os.environ.copy()
        env["KIT_GLOBAL_HOME"] = str(self.repo_root / ".kit_validation_home")
        env["KIT_BYPASS_RUNTIME_LOCK"] = "1"
        env["PYTHONUTF8"] = "1"

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def validate_component(self, name: str, command: str, cwd: Optional[Path] = None) -> ValidationResult:
        """Validate a single component."""
        start_time = datetime.now()

        success, stdout, stderr = self.run_command(command, cwd)

        duration = (datetime.now() - start_time).total_seconds()

        status = 'PASS' if success else 'FAIL'

        details = {
            'command': command,
            'stdout': stdout[-1000:] if stdout else '',  # Last 1000 chars
            'stderr': stderr[-1000:] if stderr else '',
            'exit_code': 0 if success else 1
        }

        result = ValidationResult(
            component=name,
            status=status,
            duration=duration,
            details=details,
            timestamp=start_time.isoformat()
        )

        self.results.append(result)
        return result

    def validate_semantic_contracts(self) -> ValidationResult:
        """Validate critical API contracts (e.g. recall tuple return)."""
        # Ensure recall returns the correct types (tuple when queried directly)
        # Use a more robust multi-line command
        cmd_lines = [
            "import sys",
            "from kit.core.kit_cognitive_core import SAMBrain",
            "import tempfile",
            "from pathlib import Path",
            "with tempfile.TemporaryDirectory() as tmp:",
            "    b = SAMBrain(Path(tmp)/'test.db')",
            "    res = b.recall(['test'])",
            "    if not isinstance(res, tuple) or len(res) != 2:",
            "        print(f'Contract Violation: recall returned {type(res)} instead of tuple')",
            "        sys.exit(1)",
            "    print('Contract OK')"
        ]
        cmd = f"python -c \"{'; '.join(cmd_lines)}\"".replace("with tempfile.TemporaryDirectory() as tmp:;", "with tempfile.TemporaryDirectory() as tmp:")
        # Actually, it's easier to just use a single line without 'with' or with a simpler structure
        cmd = (
            "python -c \""
            "import sys; from kit.core.kit_cognitive_core import SAMBrain; from pathlib import Path; "
            "import tempfile; tmp = tempfile.mkdtemp(); "
            "b = SAMBrain(Path(tmp)/'test.db'); "
            "res = b.recall(['test']); "
            "valid = isinstance(res, tuple) and len(res) == 2; "
            "print('Contract OK' if valid else 'FAIL'); "
            "sys.exit(0 if valid else 1)\""
        )
        return self.validate_component("Semantic Contracts", cmd)

    def validate_runtime_integrity(self) -> ValidationResult:
        """Validate core runtime components."""
        return self.validate_component(
            "Runtime Integrity",
            "python -c \"from kit.api import *; from kit.core.kit_cognitive_core import SAMBrain; print('Runtime OK')\""
        )

    def validate_flow_correctness(self) -> ValidationResult:
        """Validate flow state machine correctness."""
        return self.validate_component(
            "Flow Correctness",
            "python -m pytest tests/test_flow_v124_core.py -v --tb=short"
        )

    def validate_resilience(self) -> ValidationResult:
        """Validate system resilience under failure conditions."""
        return self.validate_component(
            "System Resilience",
            "python -m pytest tests/test_v124_resilience.py -v --tb=short"
        )

    def validate_adaptive_learning(self) -> ValidationResult:
        """Validate adaptive learning and feedback loops."""
        return self.validate_component(
            "Adaptive Learning",
            "python -m pytest tests/test_evolutionary_loop.py -v --tb=short"
        )

    def validate_deterministic_core(self) -> ValidationResult:
        """Validate deterministic behavior."""
        return self.validate_component(
            "Deterministic Core",
            "python -m pytest tests/test_deterministic.py -v --tb=short"
        )

    def validate_ci_smoke_test(self) -> ValidationResult:
        """Validate CI smoke tests (minimal example + API)."""
        # Test minimal example
        example_result = self.validate_component(
            "Minimal Example",
            "python examples/minimal_example.py"
        )

        if example_result.status == 'FAIL':
            return example_result

        # Test API imports
        return self.validate_component(
            "API Imports",
            "python -c \"from kit.api import *; print('API imports successful')\""
        )

    def validate_legacy_compatibility(self) -> ValidationResult:
        """Validate compatibility with legacy components (SKIP for now)."""
        # This would test old v1.2.3 components if needed
        return ValidationResult(
            component="Legacy Compatibility",
            status="SKIP",
            duration=0.0,
            details={"reason": "Legacy components isolated"},
            timestamp=datetime.now().isoformat()
        )

    def generate_report(self) -> SystemValidationReport:
        """Generate complete validation report."""
        # Calculate summary
        passed = sum(1 for r in self.results if r.status == 'PASS')
        failed = sum(1 for r in self.results if r.status == 'FAIL')
        skipped = sum(1 for r in self.results if r.status == 'SKIP')
        total = len(self.results)

        overall_status = 'PASS' if failed == 0 else 'FAIL'

        summary = {
            'total_components': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'success_rate': (passed / total * 100) if total > 0 else 0,
            'total_duration': sum(r.duration for r in self.results)
        }

        return SystemValidationReport(
            overall_status=overall_status,
            components=self.results,
            summary=summary,
            generated_at=datetime.now().isoformat()
        )

    def run_full_validation(self) -> SystemValidationReport:
        """Run complete validation suite."""
        print("🚀 Starting Unified Validation System v1.2.4")
        print("=" * 50)

        # Core runtime
        print("📦 Validating Runtime Integrity...")
        self.validate_runtime_integrity()

        print("📜 Validating Semantic Contracts...")
        self.validate_semantic_contracts()

        # Flow system
        print("🔄 Validating Flow Correctness...")
        self.validate_flow_correctness()

        # Resilience
        print("🛡️  Validating System Resilience...")
        self.validate_resilience()

        # Learning
        print("🧠 Validating Adaptive Learning...")
        self.validate_adaptive_learning()

        # Deterministic behavior
        print("🎯 Validating Deterministic Core...")
        self.validate_deterministic_core()

        # CI smoke tests
        print("🔥 Validating CI Smoke Tests...")
        self.validate_ci_smoke_test()

        # Legacy (skip)
        print("📜 Validating Legacy Compatibility...")
        self.validate_legacy_compatibility()

        # Generate report
        report = self.generate_report()

        print("\n" + "=" * 50)
        print(f"🎯 OVERALL STATUS: {report.overall_status}")
        print(f"📊 Success Rate: {report.summary['success_rate']:.1f}%")
        print(f"⏱️  Total Duration: {report.summary['total_duration']:.2f}s")
        print(f"✅ Passed: {report.summary['passed']}")
        print(f"❌ Failed: {report.summary['failed']}")
        print(f"⏭️  Skipped: {report.summary['skipped']}")

        return report

    def export_report(self, report: SystemValidationReport, output_path: Optional[Path] = None):
        """Export validation report to JSON."""
        if output_path is None:
            output_path = self.repo_root / "validation_report.json"

        report_dict = {
            'overall_status': report.overall_status,
            'summary': report.summary,
            'generated_at': report.generated_at,
            'components': [
                {
                    'component': r.component,
                    'status': r.status,
                    'duration': r.duration,
                    'timestamp': r.timestamp,
                    'details': r.details
                }
                for r in report.components
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2)

        print(f"📄 Report exported to: {output_path}")


def main():
    """Main entry point for unified validation."""
    validator = UnifiedValidator()
    report = validator.run_full_validation()

    # Export report
    validator.export_report(report)

    # Exit with appropriate code
    sys.exit(0 if report.overall_status == 'PASS' else 1)


if __name__ == "__main__":
    main()