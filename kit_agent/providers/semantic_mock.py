import time
from typing import Dict, Any
from kit_agent.providers.base import BaseProvider

class SemanticMockProvider(BaseProvider):
    """
    A more intelligent mock that behaves differently based on memory confidence labels in the prompt.
    Used for testing the cognitive engine's behavior.
    """
    def __init__(self, name="semantic_mock"):
        self.name = name

    def ask(self, prompt: str) -> Dict[str, Any]:
        time.sleep(0.1) # Fast simulation
        
        prompt_upper = prompt.upper()
        # Behavioral Scenarios detection
        task_is_logging = "LOGIN LOGGER" in prompt_upper or "LOGGING" in prompt_upper
        task_is_database = "DATABASE" in prompt_upper
        task_is_ui = "UI THEME" in prompt_upper
        
        # 1. HIGH CONFIDENCE: Expecting Absolute Obedience
        if "[MEMORY RULES]" in prompt_upper and "AMBIGUOUS" not in prompt_upper and "WEAK SIGNAL" not in prompt_upper:
            if task_is_database and "SQLITE" in prompt_upper:
                return {
                    "ok": True,
                    "text": "The database layer will use SQLite as a mandated invariant from memory.",
                    "error": None
                }
            if task_is_logging and "AUTH TOKENS" in prompt_upper:
                return {
                    "ok": True,
                    "text": "The login logger is implemented. As a MANDATED INVARIANT, auth tokens MUST NOT be logged to console.",
                    "error": None
                }
        
        # 2. AMBIGUOUS: Expecting Hedged Reasoning (Hard Directive)
        if "AMBIGUOUS" in prompt_upper or "CONFLICT DETECTED" in prompt_upper:
            if "CACHING" in prompt_upper:
                return {
                    "ok": True,
                    "text": "CRITICAL: CONFLICT DETECTED. Memory contains conflicting decisions for caching (Redis vs Memcached). As required by the Hard Directive, I am requesting clarification rather than making an assumption.",
                    "error": None
                }
        
        # 3. WEAK SIGNAL: Expecting Flexibility
        if "WEAK SIGNAL" in prompt_upper or "LOW CONFIDENCE" in prompt_upper:
            if task_is_logging:
                return {
                    "ok": True,
                    "text": "Considering file-based logging as it is mentioned as a potential suggestion (weak signal), rather than a strict requirement.",
                    "error": None
                }

        # Fallback to Task-aware defaults
        if task_is_logging:
            return {
                "ok": True,
                "text": "Considering file-based logging as a potential suggestion, with sensitive data checks applied.",
                "error": None,
            }
        if task_is_database:
            return {
                "ok": True,
                "text": "Database setup: Use SQLite as the mandated architectural invariant.",
                "error": None,
            }
        
        return {
            "ok": True,
            "text": "Task processed by semantic mock (Standard output).",
            "error": None
        }
