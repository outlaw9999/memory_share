"""
kit_cmc.py — KIT v1.2.5: Truth Computation Layer (CMC v1).
Calculates structural invariants and epistemic stability.
"""

from collections import Counter
from typing import Any

BLOCK_THRESHOLD = 0.2


def compute_stability(history: list[dict[str, Any]]) -> float:
    """
    CMC v1 Math: Calculate Identity Stability (S_id).
    S_id = count(primary_hash) / total_samples
    """
    if not history:
        return 1.0

    # Extract structural hashes (ignore None/Noise)
    hashes = [r.get("structural_hash") for r in history if r.get("structural_hash")]

    if not hashes:
        return 1.0  # New identity or non-structural symbol

    counts = Counter(hashes)
    most_common_count = counts.most_common(1)[0][1]

    return most_common_count / len(hashes)


def is_identity_collapsed(stability_score: float) -> bool:
    """
    Enforce the Titanium BLOCK invariant.
    If stability falls below 0.2, the symbol's identity has collapsed.
    """
    return stability_score < BLOCK_THRESHOLD
