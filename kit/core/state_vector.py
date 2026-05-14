from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StateVector:
    """
    v1.2.5 Minimum Epistemic Substrate.
    This is the GROUND TRUTH for all cognitive transitions.
    """
    symbol: str
    structural_hash: str | None
    access_count: int
    last_updated: str  # ISO timestamp from DB
    is_baked: bool
    state: str = "ALLOW"
    reason: str | None = None
    severity: str = "LOW"
    requires_review: bool = False
    conflict_ratio: float = 0.0
    stability_score: float = 1.0
