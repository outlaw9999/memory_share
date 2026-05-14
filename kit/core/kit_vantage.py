import json
import logging
import subprocess
import tempfile
from pathlib import Path

from kit.core import kit_env
from kit.models.signal import Signal

logger = logging.getLogger("kit.vantage")

# v1.2.5-TITANIUM: Unified Binary Discovery
VANTAGE_BIN = kit_env.get_vantage_bin()


def invoke_vantage(path: Path, timeout: int = 10, strict: bool = False) -> list[Signal]:
    """
    Invoke the Vantage AST Sensor (Rust) and map its output to standardized Signals.
    Implementation of Phase B 'Neural Wiring' (v1.2.5-TITANIUM).
    """
    if not VANTAGE_BIN or not VANTAGE_BIN.exists():
        msg = "Vantage binary missing. Please set VANTAGE_HOME or install to project root."
        if strict:
            raise RuntimeError(msg)
        logger.error(msg)
        return []

    if not path.exists():
        logger.error(f"Vantage invocation failed: Path not found {path}")
        return []

    cmd = [str(VANTAGE_BIN), "verify", str(path), "--json"]

    try:
        # v1.2.5: Fast-failure with strict timeout to prevent IDE/CLI hang
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)

        if result.returncode != 0:
            logger.warning(f"Vantage returned non-zero status ({result.returncode}) for {path.name}")
            return []

        if not result.stdout.strip():
            return []

        data = json.loads(result.stdout)

        signals = []
        for v_sig in data.get("signals", []):
            # Mapping Identity (UUID) and Fingerprint (Normalized Hash)
            # Architecture: Identity = UUID, Fingerprint = Normalized Hash (AST-stable)
            signals.append(
                Signal(
                    uid=f"STRUCTURAL:{v_sig['type'].upper()}",
                    confidence="high",
                    line=v_sig.get("line", 0),
                    source="vantage",
                    evidence=v_sig.get("id"),  # Store UUID as evidence for L3 reasoning
                    symbol=v_sig.get("id"),  # Identity
                    structural_hash=v_sig.get("norm_hash"),  # AST-stable fingerprint
                )
            )

        return signals

    except subprocess.TimeoutExpired:
        logger.error(f"Vantage invocation timed out after {timeout}s for {path.name}")
        return []
    except json.JSONDecodeError:
        logger.error(f"Vantage returned invalid JSON for {path.name}")
        return []
    except Exception as e:
        logger.exception(f"Unexpected error during Vantage invocation: {e}")
        return []


def invoke_vantage_on_text(code: str, suffix: str = ".py", timeout: int = 5, strict: bool = False) -> list[Signal]:
    """
    Analyzes raw code text by writing to a temporary shadow file and invoking Vantage.
    Critical for 'learn' flow enrichment where code might not be on disk yet.
    """
    try:
        # Normalize line endings to LF before sending to Vantage to ensure consistent hashing
        normalized_code = code.replace("\r\n", "\n")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, prefix="kit_v_", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(normalized_code)
            tmp_name = tmp.name

        tmp_path = Path(tmp_name)
        try:
            return invoke_vantage(tmp_path, timeout=timeout, strict=strict)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception as e:
        if strict:
            raise
        logger.error(f"Failed to analyze text via Vantage: {e}")
        return []


def get_graph(path: Path, timeout: int = 15) -> dict:
    """
    Invoke Vantage graph command (v1.2.5).
    Returns JSON graph data: {"nodes": [...], "edges": [...]}
    """
    if not VANTAGE_BIN or not VANTAGE_BIN.exists():
        raise RuntimeError("Vantage binary missing.")

    # Vantage v1.2.5 graph command requires a file target
    if path.is_dir():
        logger.warning(
            f"get_graph: target is a directory {path}. Vantage graph requires a file. Scanning entry point..."
        )
        # Fallback: look for __init__.py or main.py
        for entry in ["__init__.py", "main.py"]:
            if (path / entry).exists():
                path = path / entry
                break
        else:
            return {"nodes": [], "edges": []}

    cmd = [str(VANTAGE_BIN), "graph", str(path), "--json"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Vantage graph failed for {path}: {e}")
        return {"nodes": [], "edges": []}


def invoke_vantage_batch(items: list[dict], timeout: int = 30) -> list[list[Signal]]:
    """
    Batch version of invoke_vantage_on_text.
    items: list of {"content": str, ...}
    returns: list of signal lists [ [sig, sig], [sig], ... ]
    """
    results = []
    for item in items:
        code = item.get("content", "")
        suffix = item.get("suffix", ".py")
        results.append(invoke_vantage_on_text(code, suffix=suffix, timeout=timeout))
    return results


if __name__ == "__main__":
    # Internal diagnostic mode
    import sys

    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
        print(f"Diagnostics: Invoking Vantage on {test_path}...")
        results = invoke_vantage(test_path)
        for sig in results:
            print(f"  [SIGNAL] {sig.uid} | Symbol: {sig.symbol} | Hash: {sig.structural_hash}")
