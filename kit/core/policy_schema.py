# kit/core/policy_schema.py

from typing import List

# The "Cognitive Vocabulary" of Kit v1.2.4.
# Driven by runtime truth, shared with CLI for introspection.
LEARN_TAGS = [
    "invariant",   # Unchanging system laws
    "decision",    # Record of a tactical choice
    "friction",    # Blocks, delays, or issues found
    "preference",  # Stylistic or non-functional bias
    "note",        # General context
    "legacy",      # Outdated but relevant context
    "skill",       # Functional capability or instruction
    "pattern",     # Structural or architectural motif
    "hypothesis"   # Unverified assumptions
]

# System-level capabilities
KIT_CAPABILITIES = {
    "recall": {
        "description": "Deterministic memory retrieval for context bootstrapping.",
        "params": ["query", "--mode", "--agent"],
        "governance": "MCE-Mandatory-Gate"
    },
    "learn": {
        "description": "Persist observations and signals into project memory.",
        "params": ["--tag", "--scope", "--signal"],
        "tags": LEARN_TAGS
    }
}
