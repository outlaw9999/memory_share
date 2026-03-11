import logging
from typing import Optional

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

    def __init__(self, store, model=None):
        self.store = store
        self.grounder = GroundingEngine(self.store.conn)
        self.planner = HeuristicPlanner()
        self.graph_engine = GraphEngine(self.store)
        self.builder = ContextBuilder()

        # Tích hợp LLM reasoner, hoặc fallback về dummy.
        self.model = model or DummyModel()

    def explain(self, query: str) -> str:
        # 1. Grounding: NL -> Symbols
        grounded = self.grounder.resolve(query)
        if grounded.confidence < 0.3 or not grounded.symbols:
            return "Tôi không tìm thấy symbol liên quan. Bạn có thể cung cấp thêm tên hàm không?"

        # 2. Planning: Intent -> Traversal Strategy
        plan = self.planner.plan(grounded)

        # 3. Traversal: Thực thi Batched BFS (Tốc độ ánh sáng <10ms)
        subgraph = self.graph_engine.execute(plan)

        # 4. Context Building: Edge to Atomic Facts
        context_text = self.builder.build(subgraph)

        # 5. Reasoning: Truyền Atomic Facts vào LLM
        final_prompt = self._craft_prompt(query, context_text)
        return self.model.generate(final_prompt)

    def _craft_prompt(self, query: str, context: str) -> str:
        return f"""CONTEXT (Ground Truth from Code Graph):

{context}

QUESTION:
{query}

RULES:
1. Only use facts in CONTEXT
2. If graph is missing edge say: "Graph incomplete"
3. Do not invent functions
"""
