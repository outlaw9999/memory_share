# kit/explain/pipeline.py
from typing import Dict, Any, Callable, Optional
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
        words = query.replace("?", "").replace(".", "").replace("(", " ").replace(")", " ").split()
        # Regex heuristc: Các từ có dấu gạch dưới hoặc camelCase thường là Symbol
        symbols = [w for w in words if '_' in w or (w.islower() and len(w) > 3)]
        if not symbols:
            symbols = ["main"] # Fallback
            
        return GroundedQuery(
            original_query=query,
            intents=["explain"],
            symbols=[symbols[-1]] # Lấy từ khóa cuối cùng có vẻ giống code
        )

# Giả lập Planner (Bước 2)
class Planner:
    def plan(self, query: GroundedQuery) -> TraversalPlan:
        """
        Lập kế hoạch duyệt đồ thị. Bản production sẽ dùng Small LLM.
        """
        return TraversalPlan(
            entry_symbols=query.symbols,
            layers=[0, 1], # Lấy Structural + Assertion Graph
            max_depth=3
        )

class ExplainPipeline:
    def __init__(self, db_conn):
        self.grounder = Grounder()
        self.planner = Planner()
        self.graph_engine = GraphEngine(db_conn)
        self.context_builder = ContextBuilder()
        
    def run(self, query: str, llm_reasoner: Optional[Callable[[str], str]] = None) -> str:
        """
        Thực thi nguyên vẹn 5 bước kiến trúc Cognitive Agent.
        """
        # Bước 1: Symbol Resolution
        grounded = self.grounder.resolve(query)
        
        # Bước 2: Graph Planning
        plan = self.planner.plan(grounded)
        
        # Bước 3: Deterministic Traversal (O(1) Batched BFS)
        subgraph = self.graph_engine.execute(plan)
        
        # Bước 4: Memory Distillation (Nén Context)
        context = self.context_builder.build(subgraph)
        
        # Bước 5: LLM Reasoning
        if llm_reasoner:
            prompt = f"Facts:\n{context}\n\nQuestion:\n{query}\n\nAnswer:"
            return llm_reasoner(prompt)
        
        return context
