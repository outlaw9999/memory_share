"""
vantage_adapter.py - L2/L3 Bridge for Vantage ↔ .kit
Fixed + Safe version (2026-03-24)

Flow:
Vantage CLI → adapter (parse + filter) → .kit memory
"""

import sys
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

TOP_K = 5
MAX_WORDS = 30
ENCODING = "utf-8"

VANTAGE_BIN = Path("E:/DEV/opensource_contrib/Vantage/target/debug/vantage.exe")
BAT_SHIM = Path(__file__).parent.parent / "kit-vantage.bat"


def is_vantage_available() -> bool:
    """Check if Vantage binary is available."""
    if VANTAGE_BIN.exists():
        return True
    if BAT_SHIM.exists():
        return True
    import shutil

    return shutil.which("vantage") is not None


def get_status() -> Dict:
    """Get adapter status with graceful fallback info."""
    available = is_vantage_available()
    return {
        "adapter": "vantage",
        "version": "1.0.0",
        "available": available,
        "mode": "sensor-active" if available else "memory-only",
        "warning": None
        if available
        else "Vantage not found - running in Cognitive-Only mode. Run 'kit install-vantage' to unlock.",
    }


def fix_encoding(text: bytes) -> str:
    """Handle Windows console encoding → UTF-8."""
    encodings = ["utf-8", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            return text.decode(enc)
        except UnicodeDecodeError:
            continue
    return text.decode("utf-8", errors="replace")


def parse_vantage_text(text: str) -> Dict:
    """Parse Vantage human-readable output → structured JSON."""
    result = {
        "tool": "vantage-verify",
        "status": "unknown",
        "target": None,
        "mode": None,
        "findings": [],
        "errors": [],
    }

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("==="):
            continue

        if "Mục tiêu:" in line or "Muc tieu:" in line.replace("ụ", "u"):
            m = re.search(r'[""]?([^""]+)[""]?$', line)
            if m:
                result["target"] = m.group(1).strip()

        if "Chế độ:" in line or "Che do:" in line:
            m = re.search(r":\s*(.+)$", line)
            if m:
                result["mode"] = m.group(1).strip()

        if "Error:" in line:
            result["errors"].append(line)
            result["status"] = "error"

        if any(s in line for s in ["TRẠNG THÁI:", "TRANG THAI:"]):
            if "KHÔNG TÌM THẤY" in line or "KHONG TIM THAY" in line:
                result["status"] = "no-monitoring-region"

        if any(x in line for x in ["🔴", "🟢", "🟡"]):
            if "TRẠNG THÁI:" in line or "TRANG THAI:" in line:
                m = re.search(r":\s*(.+)$", line)
                if m:
                    result["status"] = m.group(1).strip()

    return result


def sanitize(content: str) -> str:
    """Strip dangerous chars that break CLI/shell."""
    return re.sub(r"[><&|]", "", content).strip()[:200]


def filter_signals(parsed: Dict, top_k: int = TOP_K) -> List[Dict]:
    """Extract + rank signals from parsed Vantage output with symbol binding."""
    signals = []

    target_path = parsed.get("target")
    target_file = Path(target_path).name if target_path else None

    if target_path:
        signals.append(
            {
                "type": "target",
                "priority": 1,
                "content": f"Verified: {Path(target_path).name}",
                "file": target_file,
                "symbol": f"vantage.target.{target_file}",
                "operation": "verified",
            }
        )

    if parsed.get("mode"):
        signals.append(
            {
                "type": "mode",
                "priority": 1,
                "content": f"Mode: {parsed['mode']}",
                "file": target_file,
                "symbol": f"vantage.mode",
                "operation": "detected",
            }
        )

    if parsed.get("errors"):
        for err in parsed["errors"]:
            signals.append(
                {
                    "type": "error",
                    "priority": 10,
                    "content": sanitize(err),
                    "file": target_file,
                    "symbol": "vantage.error",
                    "operation": "failed",
                }
            )

    if parsed["status"] == "no-monitoring-region":
        signals.append(
            {
                "type": "observation",
                "priority": 3,
                "content": "No @epistemic tags found in target",
                "file": target_file,
                "symbol": f"vantage.scan.{target_file}",
                "operation": "no-region",
            }
        )

    signals.sort(key=lambda s: s["priority"], reverse=True)
    return signals[:top_k]


def call_vantage(target: str) -> Dict:
    """Call Vantage CLI via shim, return parsed output with graceful fallback."""
    if not is_vantage_available():
        return {
            "tool": "vantage-verify",
            "status": "unavailable",
            "error": "Vantage not found",
            "message": "Running in memory-only mode. Run 'kit install-vantage' to enable AST scanning.",
            "target": target,
            "mode": None,
            "findings": [],
        }

    if VANTAGE_BIN.exists():
        cmd = [str(VANTAGE_BIN), "verify", target]
    elif BAT_SHIM.exists():
        cmd = ["cmd", "/c", str(BAT_SHIM), "verify", target]
    else:
        return {
            "tool": "vantage-verify",
            "status": "unavailable",
            "error": "Vantage binary not accessible",
            "message": "Check installation path",
            "target": target,
        }

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        raw = result.stdout + result.stderr
        text = fix_encoding(raw)
        return parse_vantage_text(text)
    except subprocess.TimeoutExpired:
        return {"error": "Vantage timeout"}
    except Exception as e:
        return {"error": str(e)}


def inject_to_kit(signals: List[Dict], dry_run: bool = False) -> List[str]:
    """Inject signals into .kit via atomic learns with symbol binding."""
    import kit.api as api

    injected = []

    for sig in signals:
        content = sig["content"]
        kind = sig["type"]

        symbol = sig.get("symbol")
        priority = sig.get("priority", 5)

        if len(content.split()) > MAX_WORDS:
            content = " ".join(content.split()[:MAX_WORDS])

        metadata = {
            "source": "vantage-adapter",
            "ingest": "vantage-signal",
            "priority": priority,
        }
        if sig.get("file"):
            metadata["file"] = sig["file"]
        if sig.get("operation"):
            metadata["operation"] = sig["operation"]

        if not dry_run:
            try:
                api.learn(
                    content=content,
                    kind=kind,
                    scope="vantage-signal",
                    symbol=symbol,
                    metadata=metadata,
                )
                injected.append(f"[OK] {content}")
            except Exception as e:
                injected.append(f"[FAIL] {content}: {e}")
        else:
            sym = f"@{symbol}" if symbol else ""
            injected.append(f"[DRY] {kind}{sym}: {content}")

    return injected


def safe_print(text: str):
    """Print with ASCII fallback for Windows console."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def main():
    """CLI entry: parse stdin or call Vantage directly."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "parse-stdin"

    if mode == "call":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = call_vantage(target)
    else:
        raw = sys.stdin.buffer.read()
        text = fix_encoding(raw)
        result = parse_vantage_text(text)

    signals = filter_signals(result)

    if "--dry-run" in sys.argv:
        for s in signals:
            safe_print(f"[DRY] {s['type']}: {s['content']}")
        return

    output = {"parsed": result, "signals": signals, "count": len(signals)}

    if "--json" in sys.argv:
        safe_print(json.dumps(output, ensure_ascii=False))
    else:
        for s in signals:
            safe_print(f"[{s['type']}] {s['content']}")


if __name__ == "__main__":
    main()
