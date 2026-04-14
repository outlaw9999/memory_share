import logging
from typing import Any

logger = logging.getLogger("kit.core.rmil")

# --- RMIL v1.0: Runtime Memory Injection Layer ---
# Singleton cache to store bootstrap context without redundant DB hits.

_RMIL_CACHE = {
    "skills": [],
    "facts": [],
    "loaded": False,
    "latency_ms": 0.0
}

def warmup_memory(api: Any) -> dict:
    """
    Neural Priming: Bootstrap working memory with critical context.
    Ensures agent is never in a 'Cold Start' state.
    """
    import time
    global _RMIL_CACHE
    
    if _RMIL_CACHE["loaded"]:
        return _RMIL_CACHE

    start_time = time.time()
    
    try:
        # 1. Project Procedural Skills (L3)
        # We query for procedural layer specifically to grab compiled skills
        project_skills = api.search("layer:procedural", limit=8, fast=True)
        
        # 2. Global Semantic Skills 
        global_skills = api.recall([], limit=5, with_global=True, fast=True)
        
        # 3. Identity Invariants (Constitutional Laws)
        identity = api.search("tag:invariant", limit=3, fast=True)
        
        _RMIL_CACHE["skills"] = project_skills + global_skills
        _RMIL_CACHE["facts"] = identity
        _RMIL_CACHE["loaded"] = True
        _RMIL_CACHE["latency_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"[RMIL] Warmup complete: {len(_RMIL_CACHE['skills'])} skills, "
                    f"{len(_RMIL_CACHE['facts'])} facts in {_RMIL_CACHE['latency_ms']:.2f}ms")
                    
    except Exception as e:
        logger.error(f"[RMIL] Warmup failed: {e}")
        _RMIL_CACHE["loaded"] = False
        
    return _RMIL_CACHE

def get_rmil_status() -> dict:
    """Return the current state of the working memory cache."""
    return _RMIL_CACHE
