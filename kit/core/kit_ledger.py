# kit/core/kit_ledger.py
# v1.2.5 EPISTEMIC AUTHORITY LEDGER

"""
The Single Source of Truth for immutable code invariants.
This registry replaces physical .lock files to ensure a clean, 
stateless environment for CI and verification.
"""

from typing import Dict, Final

# Certified SHA256 hashes for v1.2.5 core components
# These hashes are Git-anchored and intentionally updated only on release.
CERTIFIED_HASHES: Final[Dict[str, Dict[str, str]]] = {
    "v1.2.5": {
        "kit/core/memory_policy.py": "ce8e3c5f5f5abc4377afad64ce9e609656b4e4be71a577cdb444da1e3e4423b0",
        "kit/core/kit_cognitive_core.py": "838e5c267098e9a2638848b8981f62e84897f2c876b51558f62c0199175d7990",
    }
}


def get_certified_hash(component_path: str, version: str = "v1.2.5") -> str | None:
    """Retrieve the authority hash for a given component and version."""
    return CERTIFIED_HASHES.get(version, {}).get(component_path)
