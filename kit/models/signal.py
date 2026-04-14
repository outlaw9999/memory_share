from typing import Literal

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """
    Minimal Enforcement Contract (MEC) v1 - Signal Anchor.
    Standardized interface for v1.2.4 "Decision Discipline".
    """
    uid: str = Field(..., description="Unique ID for the violation type (e.g., SQL_04)")
    confidence: Literal["low", "medium", "high"]
    line: int
    source: str = Field(..., description="The code snippet or tool causing the smell")
    evidence: str | None = None

    # v1.2.4: Structural Integration Fields
    symbol: str | None = Field(None, description="Universal ID for the symbol identity (UUID)")
    structural_hash: str | None = Field(None, description="AST-stable structural fingerprint (Normalized Hash)")


class MecPayload(BaseModel):
    """
    The atomic payload for L2 -> L3 transport.
    """
    file_path: str
    signals: list[Signal]
    total_score_impact: float = 0.0
