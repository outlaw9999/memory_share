# kit/core/coherence_schema.py

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

class ConflictType(StrEnum):
    NONE = "none"
    SOFT = "soft"
    SEMANTIC = "semantic"
    AUTHORITY = "authority"

@dataclass
class CoherentMemory:
    key: str
    content: Any
    confidence: float
    source_tier: str
    conflict_state: str
