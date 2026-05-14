"""
Command routing table - Kit Execution Classifier
Maps commands to execution modes without AGENTS.md at runtime.
"""

COMMANDS = {
    # DIRECT: O(1) dispatch, no reasoning
    "where": {"executor": "fs", "mode": "direct"},
    # ROUTED: light graph lookup only
    "recall": {"executor": "memory", "mode": "routed"},
    # DIAGNOSTIC: full AGENTS.md reasoning (EXPLICIT ONLY)
    "doctor": {"executor": "graph", "mode": "diagnostic"},
    "learn": {"executor": "memory", "mode": "diagnostic"},
    "hygiene": {"executor": "graph", "mode": "diagnostic"},
}

# Commands outside the explicit routing table stay on the standard CLI path.
DEFAULT_MODE = "standard"
