"""Kit L0 In-Memory Cache (Stage 5.5.3).

Provides zero-latency access to the most recent uncommitted memories.
Ensures 'Immediacy' for IDE agents while 'Consistency' is handled by the Commit Layer.
"""

from __future__ import annotations
import logging
import threading
from typing import TYPE_CHECKING, List, Optional, Set

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import Memory

logger = logging.getLogger("kit.l0_cache")

class L0Cache:
    """In-memory cache for 'Hot' memories (uncommitted or just-committed)."""
    
    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self._memories: List[Memory] = []
        self._lock = threading.Lock()
        
    def push(self, memory: Memory):
        """Push a new hot memory into the cache."""
        with self._lock:
            # v1.2.4: L0 graduation (LRU-like eviction)
            if len(self._memories) >= self.max_size:
                self._memories.pop(0)
            self._memories.append(memory)

    def search(self, query: Optional[str] = None, limit: int = 10) -> List[Memory]:
        """Fast in-memory keyword search."""
        with self._lock:
            if not query:
                return self._memories[-limit:][::-1]
            
            # Simple keyword matching for L0 immediacy
            # Full FTS is handled by the SQLite (Slow Path)
            query_parts = query.lower().split()
            matches = []
            for m in reversed(self._memories):
                content_lower = m.content.lower()
                if all(part in content_lower for part in query_parts):
                    matches.append(m)
                if len(matches) >= limit:
                    break
            return matches

    def clear_by_hashes(self, structural_hashes: Set[str]):
        """Remove memories from L0 once they are committed to SQLite (Graduation)."""
        with self._lock:
            # Note: Memory object doesn't have structural_hash directly, 
            # but we can match by node_uid (which is sensor:<hash>)
            self._memories = [
                m for m in self._memories 
                if not any(h in m.node_uid for h in structural_hashes)
            ]
            
    def clear_all(self):
        """Clear the entire L0 cache."""
        with self._lock:
            self._memories.clear()
