# kit/vantage/bridge.py
# v1.2.5 — Rust backend bridge for kit-vantage.
#
# RESPONSIBILITIES (ONLY):
#   - Marshal VerificationRequest → Rust JSON input
#   - Unmarshal Rust JSON output → result dict
#   - NO business logic
#   - NO state mutation
#   - NO intent interpretation
#
# Rust is an optional backend. If unavailable, kit-vantage runs pure Python verification.

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from kit.vantage.contract import VerificationRequest

logger = logging.getLogger("kit.vantage.bridge")

_RUST_BINARY_HINTS = [
    "kit-vantage.exe",
    "../Vantage/target/release/vantage.exe",
    "../Vantage/kit-vantage.exe",
]


class RustBridge:
    """Thin FFI bridge to optional Rust verifier. Zero business logic."""

    def __init__(self, binary_path: str | None = None):
        self._binary = binary_path or self._discover()

    def verify(self, request: VerificationRequest) -> dict:
        """Marshal → subprocess → unmarshal. Pure function."""
        if not self._binary:
            return {"status": "unavailable", "confidence": 0.0, "hash": ""}

        input_json = request.to_json()
        try:
            result = subprocess.run(
                [str(self._binary), "verify", "--json"],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("Rust bridge returned %d", result.returncode)
                return {"status": "error", "confidence": 0.0, "hash": ""}
            return json.loads(result.stdout)
        except FileNotFoundError:
            logger.warning("Rust binary not found: %s", self._binary)
            return {"status": "unavailable", "confidence": 0.0, "hash": ""}
        except subprocess.TimeoutExpired:
            logger.warning("Rust bridge timed out")
            return {"status": "timeout", "confidence": 0.0, "hash": ""}
        except json.JSONDecodeError as e:
            logger.warning("Rust bridge returned invalid JSON: %s", e)
            return {"status": "error", "confidence": 0.0, "hash": ""}

    @staticmethod
    def _discover() -> str | None:
        """Search common locations for the Rust binary."""
        for hint in _RUST_BINARY_HINTS:
            p = Path(hint)
            if p.exists():
                return str(p.resolve())
        return None
