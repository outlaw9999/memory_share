import datetime
import json
import re
import sys
from pathlib import Path

# .kit v1.2.5 SHADOW - Phase 0: Raw Regex Sensors
# O(n) Complexity | Silent | Observation Only
SENSORS = {
    "SQL_INJECTION_SMELL": r"(?i)(SELECT|INSERT|UPDATE|DELETE).*(\{.*\}|\+.*|%s|\.format\()",
    "UNSAFE_PATH_USAGE": r"(?i)(open|read|write|os\.path|fs\.).*[\"'](\/|[A-Z]:\\)",
    "AUTH_BYPASS_RISK": r"app\.(get|post|put|delete)\s*\(\s*[\"'][^\"']+[\"']\s*,\s*(?!.*auth)",
}


def run_shadow_scan(filepath: str, root_path: Path):
    """
    Implements the 'Silent Sensor' hook.
    Scans the file for security smells and logs to .kit/shadow.log.
    """
    try:
        abs_path = Path(filepath)
        if not abs_path.is_absolute() and root_path:
            abs_path = root_path / filepath

        if not abs_path.exists():
            return

        with open(abs_path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
        log_path = root_path / ".kit" / "shadow.log"

        # Ensure .kit exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a", encoding="utf-8") as log_file:
            for signal, pattern in SENSORS.items():
                if re.search(pattern, content):
                    entry = {"type": signal, "file": str(filepath), "confidence": "low", "timestamp": now}
                    log_file.write(json.dumps(entry) + "\n")
    except Exception:
        # Zero-friction: Silent failure to protect the main workflow
        pass


if __name__ == "__main__":
    # Standalone execution for testing or hooks
    if len(sys.argv) > 1:
        run_shadow_scan(sys.argv[1], Path.cwd())
