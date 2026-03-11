import logging
from kit.core.grounding import GroundedQuery
from kit.schema import TraversalPlan

logger = logging.getLogger(__name__)

class HeuristicPlanner:
    """
    Kế hoạch duyệt đồ thị dựa trên Intention và Context requirement.
    Điểm nối giữa Grounding Engine và Graph Engine.
    """
    
    def plan(self, grounded: GroundedQuery) -> TraversalPlan:
        """
        Đưa ra kế hoạch duyệt graph dựa trên Intent và Grounded Symbols.
        """
        intent = grounded.intents[0] if grounded.intents else "GENERAL"

        if intent == "DEBUG":
            return TraversalPlan(
                entry_symbols=grounded.symbols,
                direction="backward",
                layers=[0, 1, 2],
                max_depth=3
            )

        if intent == "ARCHITECTURE":
            return TraversalPlan(
                entry_symbols=grounded.symbols,
                direction="forward",
                layers=[0],
                max_depth=2
            )

        if intent == "DECISION":
            return TraversalPlan(
                entry_symbols=grounded.symbols,
                direction="none",
                layers=[1, 3],
                max_depth=2
            )

        return TraversalPlan(
            entry_symbols=grounded.symbols,
            direction="bidirectional",
            layers=[0, 1],
            max_depth=2
        )
