#!/usr/bin/env python3
"""
Governance Ingester v1.2.1-Py314
Distills and ingests architectural decisions/invariants into SAMBrain.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def ingest_governance(file_path: str | None = None) -> None:
    """
    Upgraded Governance Ingester (v1.2.2)
    - Validates YAML/JSON integrity
    - Injects automated semantic tags
    - Fail-fast STDIN handling (Windows-safe)
    """
    # 1. Explicit Help / Usage
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print("Usage: kit-ingest [file_path]")
        print("Or: cat fact.yml | kit-ingest")
        sys.exit(0)

    print("[INGEST] Starting governance distillation (v1.2.2-Robust)...")

    use_yaml = False
    try:
        import yaml
        use_yaml = True
    except ImportError:
        print("[WARN] PyYAML not found. Proceeding with raw string ingestion.")

    content = ""
    try:
        if file_path and os.path.exists(file_path):
            content = Path(file_path).read_text(encoding="utf-8")
        elif not sys.stdin.isatty():
            # Robust STDIN: select () for POSIX, isatty for Windows
            if os.name != "nt":
                import select
                r, _, _ = select.select([sys.stdin], [], [], 0.2)
                if not r:
                    print("[ERROR] Timeout waiting for STDIN. (Fail-fast)")
                    sys.exit(1)
            
            try:
                content = sys.stdin.read()
            except OSError as e:
                print(f"[ERROR] Failed to read from STDIN: {e}")
                sys.exit(1)
        else:
            print("[ERROR] No input source. Use: cat fact.yml | kit-ingest")
            sys.exit(1)

        if not content.strip():
            print("[ERROR] Empty content.")
            sys.exit(1)

        if use_yaml:
            try:
                import yaml

                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    data["_metadata"] = {"ingest_source": "governance_ingest_v1.2.1p", "status": "verified"}
                    content = yaml.dump(data)
                elif isinstance(data, list):
                    content = "---\n" + yaml.dump(data)
            except yaml.YAMLError as ye:
                print(f"[ERROR] YAML Validation failed: {ye}")
                sys.exit(1)

        cmd = [sys.executable, "kit.py", "learn", "--tag", "decision", "--no-render"]
        print(f"[INGEST] Sending {len(content)} bytes to SAMBrain...")

        result = subprocess.run(
            cmd,
            input=content,
            text=True,
            capture_output=True,
            timeout=10,
        )

        if result.returncode == 0:
            print(f"[SUCCESS] {result.stdout.strip()}")
        else:
            print(f"[FAILURE] {result.stderr.strip()}")
            sys.exit(1)

    except subprocess.TimeoutExpired:
        print("[ERROR] Command timed out.")
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] I/O error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    ingest_governance(path)
