# kit/core/ipc_protocol.py
# v1.2.5: Kit ↔ Vantage IPC Protocol (MINIMAL SPEC)
#
# Design Principles:
# 1. Zero-lag priority (subprocess JSON, no socket overhead)
# 2. Vantage is black-box to Kit (strict decoupling)
# 3. Message schema versioning (future-proof)
# 4. Error taxonomy for drift detection

import json
import subprocess
from pathlib import Path
from typing import Any, Literal


# --- TRANSPORT LAYER ---

VANTAGE_BIN = "kit-vantage"


def run_vantage(args: list[str], timeout: float = 10.0) -> dict[str, Any]:
    """
    Execute Vantage CLI as subprocess, return parsed JSON.

    Returns:
        {
            "status": "ok" | "error" | "timeout",
            "data": {...} | None,
            "error": str | None,
            "latency_ms": float
        }
    """
    import time

    start = time.perf_counter()

    try:
        result = subprocess.run(
            [VANTAGE_BIN] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        latency = (time.perf_counter() - start) * 1000

        if result.returncode != 0:
            return {
                "status": "error",
                "data": None,
                "error": result.stderr.strip(),
                "latency_ms": latency,
            }

        # Try parse JSON response
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": result.stdout}

        return {
            "status": "ok",
            "data": data,
            "error": None,
            "latency_ms": latency,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "data": None,
            "error": f"Vantage execution timeout after {timeout}s",
            "latency_ms": timeout * 1000,
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "data": None,
            "error": f"Vantage binary not found: {VANTAGE_BIN}",
            "latency_ms": 0,
        }


# --- MESSAGE SCHEMA (v1) ---


class VantageRequest:
    """Request schema for Kit → Vantage communication."""

    def __init__(
        self,
        command: Literal["verify", "scan", "fingerprint"],
        path: str | Path,
        options: dict[str, Any] | None = None,
    ):
        self.command = command
        self.path = str(path)
        self.options = options or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": "v1",
            "command": self.command,
            "path": self.path,
            "options": self.options,
        }


class VantageResponse:
    """Response schema from Vantage → Kit."""

    def __init__(self, status: Literal["ok", "error", "timeout"], data: Any = None, error: str | None = None):
        self.status = status
        self.data = data
        self.error = error

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> "VantageResponse":
        return cls(
            status=result.get("status", "error"),
            data=result.get("data"),
            error=result.get("error"),
        )


# --- HIGH-LEVEL API ---


def verify_file(path: str | Path, mode: str = "safe") -> VantageResponse:
    """
    Verify a single file for structural drift.

    Args:
        path: File to verify
        mode: "safe" (fast) or "deep" (full analysis)

    Returns:
        VantageResponse with drift_score, signals, anomalies
    """
    req = VantageRequest(
        command="verify",
        path=path,
        options={"mode": mode},
    )
    result = run_vantage(["verify", str(req.path), "--mode", mode, "--json"])
    return VantageResponse.from_result(result)


def verify_directory(path: str | Path, depth: int = 5) -> VantageResponse:
    """
    Verify a directory tree for structural drift.

    Args:
        path: Root directory
        depth: Max traversal depth

    Returns:
        VantageResponse with per-file results + aggregate drift
    """
    result = run_vantage(["verify", str(path), "--recursive", "--depth", str(depth), "--json"], timeout=30.0)
    return VantageResponse.from_result(result)


def fingerprint_file(path: str | Path) -> VantageResponse:
    """
    Generate structural fingerprint for a file.

    Returns:
        VantageResponse with structural_hash, ast_summary, complexity
    """
    result = run_vantage(["fingerprint", str(path), "--json"])
    return VantageResponse.from_result(result)


# --- DRIFT DETECTION CONTRACT ---


class DriftReport:
    """Aggregated drift analysis result."""

    def __init__(self, response: VantageResponse):
        self.raw_response = response
        self.status = response.status
        self.error = response.error

        # Extract drift metrics if available
        if response.status == "ok" and response.data:
            self.files_checked = response.data.get("files_checked", 0)
            self.drift_detected = response.data.get("drift_detected", False)
            self.drift_score = response.data.get("drift_score", 0.0)
            self.signals = response.data.get("signals", [])
        else:
            self.files_checked = 0
            self.drift_detected = False
            self.drift_score = 0.0
            self.signals = []

    def is_critical(self) -> bool:
        """Drift is critical if score > 0.3"""
        return self.drift_score > 0.3

    def is_blocking(self) -> bool:
        """Drift is blocking if score > 0.7"""
        return self.drift_score > 0.7

    def summary(self) -> str:
        if self.status != "ok":
            return f"Vantage error: {self.error}"
        if self.drift_detected:
            return f"Drift detected: {self.drift_score:.2%} across {self.files_checked} files"
        return "No drift detected"


# --- ERROR TAXONOMY ---


class VantageError(Exception):
    """Base exception for Vantage IPC errors."""

    pass


class VantageNotFoundError(VantageError):
    """Vantage binary not installed."""

    pass


class VantageTimeoutError(VantageError):
    """Vantage execution exceeded timeout."""

    pass


class VantageProtocolError(VantageError):
    """Invalid response format from Vantage."""

    pass


def ensure_vantage_available() -> None:
    """Raise VantageNotFoundError if Vantage not available."""
    result = run_vantage(["--version"], timeout=5.0)
    if result["status"] == "error" and "not found" in (result["error"] or "").lower():
        raise VantageNotFoundError("Vantage not installed. Run: kit-vantage --version")
