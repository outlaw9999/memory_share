"""Release Kernel Guard (v1.2.5).

Enforces P0/P1/P2 gates as runtime invariants to ensure Global Release Safety.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("kit.release_guard")


class ReleaseGuard:
    """Authority for enforcing v1.2.5 release invariants."""

    EXPECTED_PINS = {
        "version": "1.2.5",
        "kit_schema_version": "1.2.5",
        "vantage_contract_version": "1.2.5-rust",
    }

    @classmethod
    def enforce_p0(cls, brain):
        """Hard-enforce P0 Contract Integrity."""
        try:
            with brain.get_connection(readonly=True) as conn:
                rows = conn.execute(
                    "SELECT key, value FROM kernel_metadata WHERE key IN ('version', 'kit_schema_version', 'vantage_contract_version')"
                ).fetchall()
                metadata = {r[0]: r[1] for r in rows}

                for key, expected in cls.EXPECTED_PINS.items():
                    actual = metadata.get(key)
                    if actual != expected:
                        msg = f"FATAL: P0 Violation - {key} mismatch. Expected {expected}, found {actual}."
                        logger.critical(msg)
                        sys.stderr.write(f"\n[RELEASE_GUARD] {msg}\n")
                        sys.stderr.write("[TIP] Run 'kit init' or check your environment pinning.\n")
                        sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"\n[RELEASE_GUARD] FATAL: Failed to verify P0 Contract: {e}\n")
            sys.exit(1)

    @classmethod
    def validate_vantage_seal(cls, root_path: Path):
        """Ensure a structural baseline (VANTAGE.SEAL) exists in the project root."""
        seal_path = root_path / "VANTAGE.SEAL"
        if not seal_path.exists():
            msg = "WARN: Missing VANTAGE.SEAL. Structural baseline not established."
            logger.warning(msg)
            # v1.2.5: In RC1 we only warn, but in FINAL this could become a P1 block
            return False
        return True

    @classmethod
    def check_topology_authority(cls):
        """Verify that the current process respects MemoryTopology isolation."""
        # This is a logical check that can be extended with environmental probes
        if os.getenv("KIT_BYPASS_TOPOLOGY") == "1":
            sys.stderr.write("\n[RELEASE_GUARD] FATAL: Topology bypass detected. Operation blocked.\n")
            sys.exit(1)
