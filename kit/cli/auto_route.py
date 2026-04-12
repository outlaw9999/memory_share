# .kit v1.2.3 - Minimal Governance Patch
# Guarded Auto-Routing + Cognitive Firewall + Idempotency

import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# =========================
# CONFIG
# =========================

_default_db_path = Path.home() / ".kit" / "global.db"
GLOBAL_DB_PATH: Path = (
    Path(os.getenv("KIT_HOME", "")).expanduser() / "global.db" if os.getenv("KIT_HOME") else _default_db_path
)

_default_telemetry_path = Path.home() / ".kit" / "routing_telemetry.jsonl"
TELEMETRY_PATH: Path = (
    Path(os.getenv("KIT_HOME", "")).expanduser() / "routing_telemetry.jsonl"
    if os.getenv("KIT_HOME")
    else _default_telemetry_path
)
GLOBAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CONF_THRESHOLD = 0.85

# =========================
# 🔐 FIREWALL
# =========================

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"eyJ[a-zA-Z0-9_\-]{10,}",
    r"xox[bpar]-[a-zA-Z0-9-]{10,}",  # Slack
    r"[0-9a-f]{32,}",  # Generic MD5/Hex secrets
]

SUSPICIOUS = ["api_key", "secret", "token", "password", "credential"]


def entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    probs = [c / len(text) for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs)


def strip_markdown(text: str) -> str:
    """Pre-clean layer to prevent entropy dilution from markdown symbols."""
    # remove markdown symbols
    text = re.sub(r"[#\-\*\`\n]", " ", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_secret(text: str) -> tuple[bool, str]:
    # Clean markdown
    clean_text = strip_markdown(text)

    # 1. Regex check (Global)
    for p in SECRET_PATTERNS:
        if re.search(p, clean_text):
            return True, "pattern"

    # 2. Targeted Entropy (check words following suspicious keywords)
    parts = re.split(r"[:=,\s]+", clean_text)

    for i, part in enumerate(parts):
        p_low = part.lower()
        if any(kw in p_low for kw in SUSPICIOUS):
            # Check the next part if it looks like a value
            if i + 1 < len(parts):
                val = parts[i + 1]
                if len(val) >= 8 and entropy(val) > 2.8:
                    return True, f"suspicious-value-entropy({val[:4]}...)"

    # 3. High-entropy block check (for raw secrets)
    for block in re.split(r"[\s,;]+", clean_text):
        if len(block) >= 12 and entropy(block) > 4.2:
            return True, "high-entropy-raw"

    if "://" in clean_text and "@" in clean_text:
        return True, "url-credential"

    return False, ""


# =========================
# 🗑️ NOISE FILTER
# =========================

NOISE_PATTERNS = [
    r"^i will",
    r"^here is",
    r"^output:",
    r"^done\b",
    r"^ok\b",
    r"^updated\b",
]


def detect_noise(text: str) -> bool:
    t = text.strip().lower()
    if len(t) < 20:
        return True
    for p in NOISE_PATTERNS:
        if re.match(p, t):
            return True
    return False


# =========================
# 🧠 SCORER
# =========================

GLOBAL_KW = ["must", "always", "never", "mandatory", "strictly", "invariant", "policy"]
ARCH_KW = ["architecture", "design", "standard", "protocol"]
LOCAL_KW = ["fix", "bug", "line", "error", "issue", "project", "repo", "file", "locally", "current"]


def has_code(text: str) -> bool:
    return bool(
        "`" in text
        or re.search(r"\w+\.\w+", text)
        or re.search(r"\b[a-z]+[A-Z][a-z]+\b", text)
        or re.search(r"\b[a-z]+_[a-z]+\b", text)
    )


def score(text: str) -> dict[str, float]:
    t = text.lower()
    g = s = r = 0.0

    # Generality (Global)
    g_hits = sum(1 for k in GLOBAL_KW if k in t)
    a_hits = sum(1 for k in ARCH_KW if k in t)
    g = (g_hits * 0.5) + (a_hits * 0.4)

    # Specificity (Local)
    s_hits = sum(1 for k in LOCAL_KW if k in t)
    s = s_hits * 0.3
    if has_code(text):
        s += 0.4

    if g > 0.5:
        r += 0.4

    return {"generality": min(g, 1.0), "specificity": min(s, 1.0), "reusability": min(r, 1.0)}


def decide(scores: dict[str, float]) -> tuple[str, float]:
    g = scores["generality"]
    s = scores["specificity"]

    if g >= 0.4 and s >= 0.3:
        return "AMBIGUOUS", 0.5

    if g >= 0.7 and s < 0.3:
        return "GLOBAL", g

    if s >= 0.6:
        return "LOCAL", 1.0 - g

    return "LOCAL", 0.5


# =========================
# 🧬 IDEMPOTENCY
# =========================


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_duplicate(hash_val: str) -> bool:
    if not GLOBAL_DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(str(GLOBAL_DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM observations WHERE structural_hash=? AND is_active=1", (hash_val,))
        result = cur.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False


# =========================
# 🚀 ROUTER API
# =========================


def route_content(text: str) -> dict[str, Any]:
    """Official Routing Logic for kit learn --auto"""

    # 1. Firewall
    blocked, reason = detect_secret(text)
    if blocked:
        log({"status": "BLOCKED", "reason": reason, "ts": datetime.now(UTC).isoformat()})
        return {"status": "BLOCK", "reason": reason}

    # 2. Noise
    if detect_noise(text):
        return {"status": "DROP", "reason": "noise"}

    # 3. Hash
    norm = normalize(text)
    h = sha256(norm)
    if is_duplicate(h):
        return {"status": "SKIP", "reason": "duplicate", "hash": h}

    # 4. Score
    scores = score(text)
    decision, conf = decide(scores)

    # 5. Governance override
    final = decision
    if decision == "GLOBAL" and conf < CONF_THRESHOLD:
        final = "LOCAL"

    entry = {
        "status": "OK",
        "route": final,
        "original_decision": decision,
        "confidence": round(conf, 2),
        "scores": scores,
        "hash": h,
        "ts": datetime.now(UTC).isoformat(),
    }

    log(entry)
    return entry


def log(entry: dict[str, Any]):
    try:
        with open(TELEMETRY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# =========================
# 🚀 CLI STANDALONE
# =========================


def handle():
    if sys.stdin.isatty():
        print("[FATAL] No STDIN. Use pipe.")
        sys.exit(1)

    text = sys.stdin.read()
    if not text.strip():
        print("[FATAL] Empty STDIN.")
        sys.exit(1)

    result = route_content(text)

    status = result["status"]
    if status == "BLOCK":
        print(f"[BLOCKED] Secret detected: {result['reason']}")
        sys.exit(1)
    if status == "DROP":
        print("[DROP] Noise detected.")
        return
    if status == "SKIP":
        print("[SKIP] Duplicate.")
        return

    print(f"[ROUTE] {result['route']} (conf={result['confidence']:.22f})")


if __name__ == "__main__":
    handle()
