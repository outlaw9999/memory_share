import os
import sys
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..interfaces.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)


class BrainV2Adapter(MemoryEngine):
    """
    Adapter for Brain V2 (memory_share) using direct logic imports.
    Provides <50ms latency by bypassing CLI/Subprocess overhead.
    """

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = Path(workspace_root)
        self._available = False
        self._query_func: Optional[Callable[..., Any]] = None
        self._init_engine()

    def _init_engine(self) -> None:
        """Dynamic import to maintain thin dependency boundary."""
        # Inject brain/ops into path for resolution
        ops_path = str(self.workspace_root / "brain" / "ops")
        if ops_path not in sys.path:
            sys.path.append(ops_path)

        try:
            # Import the programmatic search function
            from query_layer3 import search_metadata  # type: ignore[import-not-found]

            self._query_func = search_metadata
            self._available = True
            logger.info("Brain V2 Engine initialized via direct import.")
        except ImportError as e:
            logger.warning(
                f"Brain V2 not found or misconfigured. Status: AMNESIA. Error: {e}"
            )
            self._available = False

    def health(self) -> Dict[str, Any]:
        return {
            "name": "BrainV2_SQLite",
            "available": self._available,
            "latency": "<50ms (direct)" if self._available else "N/A",
            "workspace": str(self.workspace_root),
        }

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self._available or not self._query_func:
            return []

        try:
            # Call the programmatic entry point
            results = self._query_func(query, limit=limit)
            return self._standardize(results)
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return [{"error": str(e)}]

    def resolve(self, handle_id: str) -> Optional[Dict[str, Any]]:
        # In v0.1, the search result already contains enough snippet data.
        # Future: implement deep neuron retrieval here.
        return None

    def _standardize(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map raw Brain V2 neurons to a standard system schema."""
        standardized = []
        for item in raw_results:
            metadata = item.get("metadata", {})
            standardized.append(
                {
                    "type": "memory_neuron",
                    "handle": f"m:{item.get('neuron_id')}",
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                    "metadata": {
                        "source": metadata.get("source_path") or metadata.get("source"),
                        "heading": metadata.get("source_heading"),
                        "kind": metadata.get("source_kind"),
                        "privacy": metadata.get("privacy", "shareable"),
                    },
                }
            )
        return standardized
