from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class MemoryEngine(ABC):
    """
    Abstract interface for Semantic Memory systems.
    Any memory adapter (SQLite, VectorDB, etc.) must implement this contract.
    """

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform semantic search in memory graph."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Check memory engine status (available, latency, etc.)."""
        pass

    @abstractmethod
    def resolve(self, handle_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a memory handle into full content."""
        pass
