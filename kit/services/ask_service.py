import logging
from typing import Any, Optional

from ..services.cognitive_router import CognitiveRouter
from ..models.cognitive_bundle import CognitiveBundle

logger = logging.getLogger(__name__)


class AskService:
    """
    Orchestration layer for 'kit ask' command.
    Manages the Context Budget and ensures safe execution.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        # Placeholder: needs proper GraphStore
        self.router = CognitiveRouter(None)
        # Default budget: ~800 tokens for efficient LLM processing
        self.default_token_limit = 1000

    def query(self, text: str, explain: bool = False) -> str:
        """Execute a fused query and apply budget constraints."""
        bundle = self.router.fused_query(text)

        # Priority: Code Slice > Memory Neurons
        # If token_limit exceeded, we trim memory first, then code depth.
        # (v0.1: simple pass-through, logging for explain mode)

        if explain:
            self._log_explanation(bundle)

        return bundle

    def _log_explanation(self, bundle: Any) -> None:
        print(f"\n[Cognitive Explain]")
        print(f" - Results: {bundle[:100]}...")  # Simplified
