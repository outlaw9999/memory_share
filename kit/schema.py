from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# 1. Output of the Grounding Module
@dataclass
class GroundedQuery:
    original_query: str
    intents: List[str]            # E.g.: ["failure", "timeout"]
    symbols: List[int]            # Symbol IDs natively resolved
    scope_hint: Optional[str] = None # E.g.: "payment_flow"
    confidence: float = 1.0

# 2. Output of the Planner Module (Input for Graph Engine)
@dataclass
class TraversalPlan:
    entry_symbols: List[int]      # Symbol IDs
    layers: List[int]             # 0: Structural, 1: Assertion, 2: Causal, 3: Procedural
    direction: str = "forward"    # "forward", "backward", "bidirectional"
    max_depth: int = 3
    conditions: Dict[str, str] = field(default_factory=dict)

# 3. Output of Graph Engine (Input for Context Builder)
@dataclass
class SubgraphContext:
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    layer_sources: List[int]
