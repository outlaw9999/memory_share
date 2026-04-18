#!/usr/bin/env python3
"""
Release Verification v1.2.4 - Single Source of Truth

This script delegates to the unified validation system.
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Run unified validation for release verification."""
    repo_root = Path(__file__).resolve().parents[1]

    # Run unified validator
    result = subprocess.run(
        [sys.executable, "scripts/unified_validator.py"],
        cwd=str(repo_root),
        capture_output=False  # Let output show to user
    )

    sys.exit(result.returncode)

if __name__ == "__main__":
    main()