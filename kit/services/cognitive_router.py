import logging
from typing import Any, Optional

from kit.core.grounding import GroundingEngine
from kit.planning.planner import HeuristicPlanner
from kit.graph.engine import GraphEngine
from kit.context.builder import ContextBuilder

logger = logging.getLogger(__name__)


class DummyModel:
    def generate(self, prompt: str) -> str:
        return "[Placeholder LLM Response: Context Built Successfully]"


class CognitiveRouter:
    """
    Nhạc trưởng điều phối Hot Path của hệ thống V1:
    NL Query ➔ Grounding ➔ Planning ➔ Traversal ➔ Context ➔ LLM.
    """

    def __init__(self, store: Any, model: Optional[Any] = None) -> None:
        self.store = store
        self.grounder = GroundingEngine(self.store.conn)
        self.planner = HeuristicPlanner()
        self.graph_engine = GraphEngine(self.store)
        self.builder = ContextBuilder()

        # Tích hợp LLM reasoner, hoặc fallback về dummy.
        self.model = model or DummyModel()

    def explain(self, query: str) -> str:
        # 1. Grounding: NL -> Symbols
        grounded = self.grounder.detect_intent(query)
        # Placeholder: full grounding not implemented
        return f"Query: {query}"

    def fused_query(self, query: str) -> str:
        """Combined search: Grounding + Graph + LLM."""
        # 1. Grounding: Intent detection
        intent = self.grounder.detect_intent(query)

        # 2. Extract keywords
        keywords = self.grounder.extract_keywords(query)

        # 3. Search graph
        results = []
        for kw in keywords:
            symbols = self.store.search_symbols(kw, limit=3)
            results.extend(symbols)

        # 4. Build context
        context = "\n".join([f"- {s.name}" for s in results[:10]])

        return f"Intent: {intent}\nKeywords: {keywords}\n\nResults:\n{context}"
