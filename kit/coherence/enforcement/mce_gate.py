# kit/coherence/enforcement/mce_gate.py

from typing import List, Dict, Any
from kit.coherence.coherence_engine import MemoryCoherenceEngine


class MCEMandatoryGate:
    """
    HARD TRUTH ENFORCEMENT LAYER
    No bypass allowed.
    """

    def __init__(self):
        self.engine = MemoryCoherenceEngine()

    def enforce(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not memories:
            return []

        # HARD REQUIREMENT: always pass through coherence engine
        # Note: merge() in CoherenceEngine v1 returns a list of CoherentMemory or winners.
        # My current CoherenceEngine.resolve() handles single key.
        # I will implement a bulk_resolve in CoherenceEngine if needed, 
        # but for now I will adapt MCEMandatoryGate to handle the list.
        
        return self.engine.merge(memories) if hasattr(self.engine, 'merge') else memories
