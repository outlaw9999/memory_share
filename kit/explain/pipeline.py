# kit/explain/pipeline.py
from typing import Any, Callable, Dict, List, Optional

from kit.schema import GroundedQuery, TraversalPlan
from kit.graph.engine import GraphEngine
from kit.context.builder import ContextBuilder


# Giả lập Grounding (Bước 1)
class Grounder:
    def resolve(self, query: str) -> GroundedQuery:
        """
        Phân giải ngôn ngữ tự nhiên thành Symbols.
        Bản Prototype dùng regex tách từ đơn giản.
        """
        words = (
            query.replace("?", "")
            .replace(".", "")
            .replace("(", " ")
            .replace(")", " ")
            .split()
        )
        # Regex heuristc: Các từ có dấu gạch dưới hoặc camelCase thường là Symbol
        symbols: List[str] = [
            w for w in words if "_" in w or (w.islower() and len(w) > 3)
        ]
        if not symbols:
            symbols = ["main"]  # Fallback

        return GroundedQuery(
            original_query=query,
            intents=["explain"],
            symbols=[0],  # Placeholder: prototype uses strings, schema expects int
        )


class GraphPlanner:
    def plan(self, query: GroundedQuery) -> TraversalPlan:
        """
        Lập kế hoạch duyệt đồ thị. Bản production sẽ dùng Small LLM.
        """
        return TraversalPlan(
            entry_symbols=[0],  # Placeholder
            layers=[0, 1],  # Lấy Structural + Assertion Graph
            max_depth=3,
        )


class ExplainPipeline:
    def __init__(self, db_conn: Any) -> None:
        self.grounder = Grounder()
        self.planner = GraphPlanner()
        self.graph_engine = GraphEngine(db_conn)
        self.context_builder = ContextBuilder()

    def run(
        self, query: str, llm_reasoner: Optional[Callable[[str], str]] = None
    ) -> str:
        """
        Thực thi nguyên vẹn 5 bước kiến trúc Cognitive Agent.
        """
        # Bước 1: Symbol Resolution
        grounded = self.grounder.resolve(query)

        # Bước 2: Planning
        plan = self.planner.plan(grounded)

        # Bước 3: Graph Traversal (Placeholder)
        subgraph: Dict[str, Any] = {"edges": []}  # Placeholder

        # Bước 4: Context Building
        context = self.context_builder.build(subgraph)

        # Bước 5: LLM Reasoning (nếu có)
        if llm_reasoner:
            return llm_reasoner(context)

        return context
