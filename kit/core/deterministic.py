from __future__ import annotations

import json
import hashlib
from typing import Any

# =========================
# Deterministic JSON
# =========================

def deterministic_json(data: Any) -> str:
    """
    Serialize JSON deterministically.

    Guarantees:
    - sorted keys
    - no whitespace drift
    - stable string output
    """

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True
    )


# =========================
# Stable Hash (BLAKE2b)
# =========================

def stable_hash(text: str) -> str:
    """
    Compute deterministic hash.

    Uses:
    hashlib.blake2b (stdlib, fast, dependency-free)
    """

    h = hashlib.blake2b(
        text.encode("ascii"),
        digest_size=32
    )

    return h.hexdigest()


# =========================
# Stable Sort Contract
# =========================

def stable_sort_key(item: dict) -> tuple:
    """
    Global sorting contract.

    Required fields:
    - importance
    - created_at
    - uid
    - id
    """

    return (
        -int(item.get("importance", 0)),
        item.get("created_at", ""),
        item.get("uid", ""),
        int(item.get("id", 0)),
    )
