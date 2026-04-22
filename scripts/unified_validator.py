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
import tempfile
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
        # v1.2.4-PURE: Use a fresh, random temp directory for absolute statelessness
        self._temp_dir = tempfile.TemporaryDirectory(prefix="kit_val_")
        self.validation_home = Path(self._temp_dir.name)

    def run_command(self, cmd: str | list, cwd: Optional[Path] = None) -> tuple[bool, str, str]:
        """Run a command and return success status, stdout, stderr.
        
        Accepts either a list of args (preferred, cross-platform safe) or
        a simple string command for backward compat (no quoting/spaces in args).
        """
        if cwd is None:
            cwd = self.repo_root

        # v1.2.4-STRICT-CONTRACT: Use the exact same interpreter for all steps
        env = os.environ.copy()
        env["KIT_BYPASS_RUNTIME_LOCK"] = "1"
        env["KIT_GLOBAL_HOME"] = str(self.validation_home / "global")
        env["KIT_LOCAL_HOME"] = str(self.validation_home / "local")
        env["PYTHONPATH"] = str(self.repo_root)
        env["PYTHONUTF8"] = "1"

        # Build list args — safe for all platforms with spaces in paths
        if isinstance(cmd, list):
            args = cmd
        else:
            # Simple split only; callers must NOT include spaces-in-paths in string form
            import shlex
            args = shlex.split(cmd, posix=(os.name == 'posix'))

        try:
            import subprocess
            result = subprocess.run(
                args,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def get_pytest_cmd(self) -> list:
        """Standardized pytest args via current interpreter."""
        return [sys.executable, "-m", "pytest"]

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
        snippet = (
            "import sys; from kit.core.kit_cognitive_core import SAMBrain; from pathlib import Path; "
            "import tempfile; tmp = tempfile.mkdtemp(); "
            "b = SAMBrain(Path(tmp)/'test.db'); "
            "res = b.recall(['test']); "
            "valid = isinstance(res, (list, tuple)); "
            "print('Contract OK' if valid else 'FAIL'); "
            "sys.exit(0 if valid else 1)"
        )
        return self.validate_component("Semantic Contracts", [sys.executable, "-c", snippet])

    def validate_runtime_integrity(self) -> ValidationResult:
        """Validate core runtime components."""
        snippet = "from kit.api import *; from kit.core.kit_cognitive_core import SAMBrain; print('Runtime OK')"
        return self.validate_component(
            "Runtime Integrity",
            [sys.executable, "-c", snippet]
        )

    def validate_flow_correctness(self) -> ValidationResult:
        """Validate flow state machine correctness."""
        return self.validate_component(
            "Flow Correctness",
            self.get_pytest_cmd() + [str(self.repo_root / 'tests' / 'test_flow_v124_core.py'), "-v", "--tb=short"]
        )

    def validate_resilience(self) -> ValidationResult:
        """Validate system resilience under failure conditions."""
        return self.validate_component(
            "System Resilience",
            self.get_pytest_cmd() + [str(self.repo_root / 'tests' / 'test_v124_resilience.py'), "-v", "--tb=short"]
        )

    def validate_adaptive_learning(self) -> ValidationResult:
        """Validate adaptive learning and feedback loops."""
        test_path = self.repo_root / 'tests' / 'research' / 'data' / 'test_evolutionary_loop.py'
        if not test_path.exists():
            return ValidationResult(
                component="Adaptive Learning",
                status="SKIP",
                duration=0.0,
                details={"reason": "test file not found (may have been removed)"},
                timestamp=datetime.now().isoformat()
            )
        return self.validate_component(
            "Adaptive Learning",
            self.get_pytest_cmd() + [str(test_path), "-v", "--tb=short"]
        )

    def validate_deterministic_core(self) -> ValidationResult:
        """Validate deterministic behavior."""
        return self.validate_component(
            "Deterministic Core",
            self.get_pytest_cmd() + [str(self.repo_root / 'tests' / 'test_deterministic.py'), "-v", "--tb=short"]
        )

    def validate_ci_smoke_test(self) -> ValidationResult:
        """Validate CI smoke tests (minimal example + API)."""
        example_result = self.validate_component(
            "Minimal Example",
            [sys.executable, str(self.repo_root / "examples" / "minimal_example.py")]
        )

        if example_result.status == 'FAIL':
            return example_result

        api_snippet = "from kit.api import *; print('API imports successful')"
        return self.validate_component(
            "API Imports",
            [sys.executable, "-c", api_snippet]
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

    def print_fingerprint(self):
        """Print environment fingerprint for CI debugging."""
        print("--- ENVIRONMENT FINGERPRINT ---")
        print(f"Python: {sys.executable}")
        print(f"Version: {sys.version.splitlines()[0]}")
        print(f"Repo Root: {self.repo_root}")
        print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")
        print(f"Validation Home: {self.validation_home}")
        print("-------------------------------\n")

    def run_full_validation(self) -> SystemValidationReport:
        """Run complete validation suite."""
        self.print_fingerprint()
        print(">>> Starting Unified Validation System v1.2.4")
        print("=" * 50)

        # Core runtime
        print("[RUNTIME] Validating Runtime Integrity...")
        self.validate_runtime_integrity()

        print("[CONTRACT] Validating Semantic Contracts...")
        self.validate_semantic_contracts()

        # Flow system
        print("[FLOW] Validating Flow Correctness...")
        self.validate_flow_correctness()

        # Resilience
        print("[RESILIENCE] Validating System Resilience...")
        self.validate_resilience()

        # Learning
        print("[LEARNING] Validating Adaptive Learning...")
        self.validate_adaptive_learning()

        # Deterministic behavior
        print("[DETERMINISM] Validating Deterministic Core...")
        self.validate_deterministic_core()

        # CI smoke tests
        print("[SMOKE] Validating CI Smoke Tests...")
        self.validate_ci_smoke_test()

        # Legacy (skip)
        print("[LEGACY] Validating Legacy Compatibility...")
        self.validate_legacy_compatibility()

        # Generate report
        report = self.generate_report()

        print("\n" + "=" * 50)
        print(f"OVERALL STATUS: {report.overall_status}")
        print(f"Summary: Success Rate: {report.summary['success_rate']:.1f}%")
        print(f"Total Duration: {report.summary['total_duration']:.2f}s")
        print(f"Passed: {report.summary['passed']}")
        print(f"Failed: {report.summary['failed']}")
        print(f"Skipped: {report.summary['skipped']}")

        if report.overall_status == 'FAIL':
            print("\n!!! FAILURE DETAILS !!!")
            for r in report.components:
                if r.status == 'FAIL':
                    print(f"\n[FAIL] {r.component}")
                    print(f"Command: {r.details['command']}")
                    print(f"Error: {r.details['stderr']}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!\n")

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

        print(f"Report exported to: {output_path}")


def main():
    """Main entry point for unified validation."""
    # Cleanup is handled by TemporaryDirectory
    validator = UnifiedValidator()
    try:
        report = validator.run_full_validation()
        # Export report
        validator.export_report(report)
        # Exit with appropriate code
        sys.exit(0 if report.overall_status == 'PASS' else 1)
    finally:
        # Explicit cleanup if needed, though TemporaryDirectory handles it
        pass


if __name__ == "__main__":
    main()