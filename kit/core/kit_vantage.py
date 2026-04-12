import json
import logging
import subprocess
from pathlib import Path

from kit.models.signal import Signal

logger = logging.getLogger("kit.vantage")

# Path to the Vantage binary - determined at runtime or via environment
VANTAGE_BIN = Path(r"E:\DEV\opensource_contrib\Vantage\target\release\vantage-verify.exe")


def invoke_vantage(path: Path, timeout: int = 10) -> list[Signal]:
    """
    Invoke the Vantage AST Sensor (Rust) and map its output to standardized Signals.
    Implementation of Phase B 'Neural Wiring' (v1.2.4-TITANIUM).
    """
    if not path.exists():
        logger.error(f"Vantage invocation failed: Path not found {path}")
        return []

    cmd = [str(VANTAGE_BIN), str(path), "--json"]
    
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
                    line=0,  # Vantage currently returns 0-indexed or block-level targets
                    source="vantage",
                    evidence=v_sig.get("id"),  # Store UUID as evidence for L3 reasoning
                    symbol=v_sig.get("id"),     # Identity
                    structural_hash=v_sig.get("normalized_hash") # AST-stable fingerprint
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

if __name__ == "__main__":
    # Internal diagnostic mode
    import sys
    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
        print(f"Diagnostics: Invoking Vantage on {test_path}...")
        results = invoke_vantage(test_path)
        for sig in results:
            print(f"  [SIGNAL] {sig.uid} | Symbol: {sig.symbol} | Hash: {sig.structural_hash}")
