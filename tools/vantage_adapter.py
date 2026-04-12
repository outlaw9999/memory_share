"""
vantage_adapter.py - L2/L3 Bridge for Vantage v1.2.3 ↔ .kit
Optimized for: Structural Signals, L1/L2 Hashing, and Zero-Base Cognitive Memory.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# --- Configuration (Standardized for v1.2.4-GOLD) ---
VANTAGE_SHIM = "kit-vantage.bat" if Path("kit-vantage.bat").exists() else "kit-vantage"
ENCODING = "utf-8"
TOP_K = 10


def run_safe(cmd: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess:
    """Safely run a subprocess, handling common errors for the v1.2.4 sensor."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=ENCODING,
            errors="replace",
            timeout=timeout,
            check=False,
            shell=sys.platform == "win32",  # Required for calling .bat from Python on Windows
        )
    except Exception as e:
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr=str(e))


def discover_signals(target_path: str) -> list[dict]:
    """
    Calls Vantage v1.2.3 with --json and returns a list of .kit observations.
    Implements the "Calibrated Instrument" spec.
    """
    # We use 'kit-vantage' as the command.
    # On Windows, subprocess.run handles .bat if shell=True is NOT used if called correctly,
    # but using 'kit-vantage' usually requires shell=True or the full path.
    # To maintain the "Magic" of the shim, we call it directly.
    cmd = [VANTAGE_SHIM, "verify", target_path, "--json"]
    result = run_safe(cmd)

    if result.returncode != 0:
        return []

    try:
        data = json.loads(result.stdout)
        signals_data = data.get("signals", [])

        # If signals is a count (from summary CLI), we can't do much.
        # But if it's a list (from detailed CLI/shim), we process it.
        if not isinstance(signals_data, list):
            return []

        signals = []
        for s in signals_data:
            # Map StructuralSignal to .kit Cognitive Memory
            signal_name = s.get("name", "unknown")
            signal_type = s.get("type", "observation")

            # Formatting the content according to "Calibrated Instrument" report
            content = f"VANTAGE SEAL: {signal_type.upper()} '{signal_name}' verified."

            signals.append(
                {
                    "uid": f"vantage.{signal_name}",
                    "kind": "observation",
                    "tag": "invariant",  # Standard for v1.2.3 Sealing
                    "content": content,
                    "importance": 0.9,
                    "metadata": {
                        "vantage_id": s.get("id"),
                        "structural_hash": s.get("structural_hash"),  # L1
                        "normalized_hash": s.get("normalized_hash"),  # L2
                        "signature": s.get("signature"),
                        "language": data.get("language"),
                        "target": target_path,
                    },
                }
            )
        return signals
    except (json.JSONDecodeError, KeyError):
        return []


def inject_to_kit(signals: list[dict]):
    """Injects high-fidelity signals into the .kit kernel."""
    import kit.api as api

    for sig in signals:
        try:
            # We use the raw hashes in the learn call if supported,
            # otherwise they reside in metadata for v1.2.4 analysis.
            api.learn(
                uid=sig["uid"],
                content=sig["content"],
                kind=sig["kind"],
                tag=sig["tag"],
                importance=sig["importance"],
                metadata=sig["metadata"],
            )
            print(f"✓ Ingested: {sig['uid']}")
        except Exception as e:
            print(f"✗ Failed: {sig['uid']} ({e})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python vantage_adapter.py <file-to-verify>")
        return

    target = sys.argv[1]
    print(f"🔍 Vantage v1.2.4 scanning (via {VANTAGE_SHIM}): {target}")

    signals = discover_signals(target)

    if not signals:
        print("✅ No structural maverick detected (or no @epistemic tags).")
        return

    print(f"🛡️  Found {len(signals)} structural signals. Ingesting to .kit...")
    inject_to_kit(signals)
    print("🏁 Sync complete.")


if __name__ == "__main__":
    main()
