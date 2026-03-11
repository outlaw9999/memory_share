import time
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class CognitiveBundle:
    """
    Unified container for cross-graph results (Code Graph + Memory Graph).
    Immutable (frozen=True) for safer orchestration and debugging.
    """
    query: str
    code_slice: Dict[str, Any] = field(default_factory=dict)
    memory_neurons: List[Dict[str, Any]] = field(default_factory=list)
    memory_status: str = "unknown"
    conflicts: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def token_estimate(self) -> int:
        """
        Estimate token cost for LLM context prioritization.
        Tailored for code vs. text density.
        """
        # Code: ~3 chars/token, Text: ~4 chars/token
        code_str = json.dumps(self.code_slice)
        mem_str = json.dumps(self.memory_neurons)
        
        code_tokens = len(code_str) // 3
        mem_tokens = len(mem_str) // 4
        
        return code_tokens + mem_tokens

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["estimated_tokens"] = self.token_estimate()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
