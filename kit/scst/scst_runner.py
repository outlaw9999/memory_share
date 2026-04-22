from typing import List, Dict, Any
from kit.core.memory_policy import MemoryPolicy

class SCSTRunner:
    """
    SCST Core Fuzzing Harness (v1.2.4-COLLAPSE).
    Stresses the MemoryPolicy kernel with adversarial truth candidates.
    """
    def __init__(self, router, injector):
        self.router = router
        self.injector = injector

    def run_fuzz_cycle(self, candidates: List[Any]) -> Dict[str, Any]:
        """
        Executes a single arbitration fuzzing cycle.
        """
        try:
            winner = MemoryPolicy.resolve(candidates)
            return {
                "status": "ok",
                "winner_tier": getattr(winner, 'brain_source', 'unknown') if winner else None,
                "winner_score": MemoryPolicy.calculate_score(winner) if winner else 0.0
            }
        except Exception as e:
            return {"status": "failure", "error": str(e)}
