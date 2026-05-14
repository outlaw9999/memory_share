import math
from typing import Any

from kit.core.identity_guard import check_identity_hijack, validate_authority
from kit.core.kit_cmc import compute_stability, is_identity_collapsed
from kit.core.state_vector import StateVector


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    GREEN #2: Strict Input Sanitization.
    Converts raw dirty data into deterministic safe states.
    """
    clean = row.copy()

    # 1. Access Count hygiene
    count = row.get("access_count", 0)
    try:
        clean["access_count"] = max(0, int(count)) if count is not None else 0
    except (ValueError, TypeError):
        clean["access_count"] = 0

    # 2. Structural Hash hygiene
    h = row.get("structural_hash")
    if h is None or (isinstance(h, float) and math.isnan(h)):
        clean["structural_hash"] = None
    else:
        clean["structural_hash"] = str(h)

    # 3. Symbol hygiene
    symbol = row.get("symbol")
    if not symbol or not str(symbol).strip():
        clean["symbol"] = "anonymous"
    else:
        clean["symbol"] = str(symbol).strip()

    # 4. Bake status hygiene
    clean["is_baked"] = 1 if row.get("is_baked") in (1, True, "1") else 0

    return clean


def _calculate_conflict(history: list[dict[str, Any]]) -> float:
    """
    GREEN #2: Statistical Inconsistency Indicator.
    conflict_ratio = mismatched_signals / total_signals
    """
    if not history or len(history) < 2:
        return 0.0

    hashes = [r.get("structural_hash") for r in history if r.get("structural_hash")]
    if not hashes:
        return 0.0

    # Ratio of signals that differ from the most common signal
    from collections import Counter
    counts = Counter(hashes)
    most_common_count = counts.most_common(1)[0][1]

    return 1.0 - (most_common_count / len(hashes))


def compute_state_vector(
    row: dict[str, Any],
    anchor_row: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None
) -> StateVector:
    """
    Hydrate a StateVector with Full Epistemic Enforcement (Titanium v1.2.5).
    1. Sanitization (Hygiene)
    2. Authority check (Security)
    3. Hijack detection (Integrity)
    4. Stability computation (Math)
    5. BLOCK enforcement (Policy)
    """
    # 🧼 Step 0: Sanitization (Input Hygiene)
    clean_row = _sanitize_row(row)

    symbol = clean_row["symbol"]
    proposed_hash = clean_row["structural_hash"]
    proposed_baked = bool(clean_row["is_baked"])
    agent_id = row.get("agent_id")

    # 🛡️ Step 1: Authority Gate
    is_baked = proposed_baked
    if proposed_baked and not validate_authority(agent_id, proposed_baked):
        is_baked = False

    # 🛡️ Step 2: Identity Hijack Check
    anchor_hash = anchor_row.get("structural_hash") if anchor_row else None
    forensic = check_identity_hijack(symbol, proposed_hash, anchor_hash)

    # 📡 Step 3: Conflict Metric
    conflict = _calculate_conflict(history) if history else 0.0

    # ⚖️ Step 4: Stability Math (CMC v1)
    stability = compute_stability(history) if history else 1.0

    # 🛑 Step 5: Final Policy Enforcement (BLOCK)
    state = forensic.get("state", "ALLOW")
    reason = forensic.get("reason")
    severity = forensic.get("severity", "LOW")
    requires_review = forensic.get("requires_review", False)

    if is_identity_collapsed(stability):
        state = "BLOCK"
        reason = "IDENTITY_COLLAPSE"
        severity = "HIGH"
        requires_review = True

    return StateVector(
        symbol=symbol,
        structural_hash=proposed_hash,
        access_count=clean_row["access_count"],
        last_updated=row.get("created_at", ""),
        is_baked=is_baked,
        conflict_ratio=conflict,
        stability_score=stability,
        state=state,
        reason=reason,
        severity=severity,
        requires_review=requires_review
    )
