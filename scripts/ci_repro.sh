#!/bin/bash
# CI Repro Harness v1.2.4 (Linux/macOS)
# Replicates GitHub Actions 'Royal Guard' flow locally

set -e

echo ">>> Starting CI Repro Harness (DER v1)"

# 1. Sync dependencies
echo -e "\n[1/3] Syncing dependencies..."
uv sync --all-extras

# 2. Fingerprint
echo -e "\n[2/3] Environment Fingerprint..."
uv run python -c "import sys; print(f'Interpreter: {sys.executable}'); print(f'Version: {sys.version}')"
uv run python -c "import os; print('PYTHONPATH:', os.environ.get('PYTHONPATH'))"

# 3. Validate
echo -e "\n[3/3] Running Unified Validator..."
export PYTHONUTF8=1
uv run python -m scripts.unified_validator

echo -e "\n✅ CI Repro: PASS"
