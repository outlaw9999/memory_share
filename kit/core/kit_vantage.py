import json
import logging
import subprocess
import tempfile
from pathlib import Path

from kit.core import kit_env
from kit.models.signal import Signal

logger = logging.getLogger("kit.vantage")

# v1.2.4-TITANIUM: Unified Binary Discovery
VANTAGE_BIN = kit_env.get_vantage_bin()


def invoke_vantage(path: Path, timeout: int = 10, strict: bool = False) -> list[Signal]:
    """
    Invoke the Vantage AST Sensor (Rust) and map its output to standardized Signals.
    Implementation of Phase B 'Neural Wiring' (v1.2.4-TITANIUM).
    """
    if not VANTAGE_BIN or not VANTAGE_BIN.exists():
        msg = f"Vantage binary missing. Please set VANTAGE_HOME or install to project root."
        if strict:
            raise RuntimeError(msg)
        logger.error(msg)
        return []

    if not path.exists():
        logger.error(f"Vantage invocation failed: Path not found {path}")
        return []

    cmd = [str(VANTAGE_BIN), "verify", str(path), "--json"]

    try:
        # v1.2.4: Fast-failure with strict timeout to prevent IDE/CLI hang
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

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
                    symbol=v_sig.get("id"),     # Identity
                    structural_hash=v_sig.get("norm_hash")  # AST-stable fingerprint
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

        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, prefix="kit_v_", delete=False, encoding="utf-8") as tmp:
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


def invoke_vantage_batch(items: list[dict], timeout: int = 10) -> list[list[Signal]]:
    """
    Batch Verification Gate (v1.2.4-TITANIUM).
    Analyzes multiple code snippets in a single Rust IPC call to eliminate per-call lag.
    
    Args:
        items: List of dicts with {"content": str, "id": any}
        
    Returns:
        List of signal lists, one for each input item.
    """
    if not items:
        return []
    if not VANTAGE_BIN or not VANTAGE_BIN.exists():
        return [[] for _ in items]

    # Step 1: Concatenate with clear boundaries to preserve structural context
    # v1.2.4 Standard: Use 3 newlines + comment block as boundary
    full_code = ""
    offsets = []
    
    for i, item in enumerate(items):
        content = item.get("content", "").replace("\r\n", "\n")
        start_line = full_code.count("\n") + 1
        full_code += f"\n# --- BATCH_ITEM_{i} ---\n"
        full_code += content
        full_code += "\n"
        end_line = full_code.count("\n")
        offsets.append({"start": start_line, "end": end_line, "index": i})

    # Step 2: Invoke Vantage once
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix="kit_v_batch_", delete=False, encoding="utf-8") as tmp:
            tmp.write(full_code)
            tmp_path = Path(tmp.name)

        try:
            all_signals = invoke_vantage(tmp_path, timeout=timeout)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        # Step 3: Map signals back to items
        results = [[] for _ in items]
        for sig in all_signals:
            for off in offsets:
                if off["start"] <= sig.line <= off["end"]:
                    # Shift line number back to relative
                    sig.line = sig.line - off["start"] - 1
                    results[off["index"]].append(sig)
                    break
        return results

    except Exception as e:
        logger.error(f"Batch Vantage Gate failed: {e}")
        return [[] for _ in items]


if __name__ == "__main__":
    # Internal diagnostic mode
    import sys
    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
        print(f"Diagnostics: Invoking Vantage on {test_path}...")
        results = invoke_vantage(test_path)
        for sig in results:
            print(f"  [SIGNAL] {sig.uid} | Symbol: {sig.symbol} | Hash: {sig.structural_hash}")
