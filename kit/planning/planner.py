import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class HeuristicPlanner:
    """
    Kế hoạch duyệt đồ thị dựa trên Intention và Context requirement.
    Điểm nối giữa Grounding Engine và Graph Engine.
    """

    def plan(self, grounded: Dict[str, Any]) -> Dict[str, Any]:
        """
        Đưa ra kế hoạch duyệt graph dựa trên Intent và Grounded Symbols.
        """
        intent = (
            grounded.get("intents", ["GENERAL"])[0]
            if isinstance(grounded.get("intents"), list)
            else "GENERAL"
        )

        if intent == "DEBUG":
            return {
                "entry_symbols": grounded.get("symbols", []),
                "layers": [0, 1, 2],
                "direction": "backward",
                "max_depth": 5,
            }
        elif intent == "ARCHITECTURE":
            return {
                "entry_symbols": grounded.get("symbols", []),
                "layers": [0],
                "direction": "bidirectional",
                "max_depth": 3,
            }
        else:
            return {
                "entry_symbols": grounded.get("symbols", []),
                "layers": [0, 1],
                "direction": "forward",
                "max_depth": 2,
            }
