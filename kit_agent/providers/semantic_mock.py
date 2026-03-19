import time
import json
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
                    "text": json.dumps({
                        "decision": "PASS",
                        "reason": "Use SQLite as the mandated invariant from memory.",
                        "confidence": 0.98,
                    }),
                    "error": None
                }
            if task_is_logging and "AUTH TOKENS" in prompt_upper:
                return {
                    "ok": True,
                    "text": json.dumps({
                        "decision": "BLOCK",
                        "reason": "Auth tokens must not be logged because this violates a mandated invariant.",
                        "confidence": 0.99,
                        "violations": ["Auth tokens MUST NOT be logged to console."],
                    }),
                    "error": None
                }
            if "JWT" in prompt_upper and "COOKIE" in prompt_upper:
                return {
                    "ok": True,
                    "text": json.dumps({
                        "decision": "BLOCK",
                        "reason": "Cookies conflict with the JWT-only invariant.",
                        "confidence": 0.99,
                        "violations": ["Auth must use JWT."],
                    }),
                    "error": None,
                }
        
        # 2. AMBIGUOUS: Expecting Hedged Reasoning (Hard Directive)
        if "AMBIGUOUS" in prompt_upper or "CONFLICT DETECTED" in prompt_upper:
            if "CACHING" in prompt_upper:
                return {
                    "ok": True,
                    "text": json.dumps({
                        "decision": "WARN",
                        "reason": "Conflict detected between Redis and Memcached; requesting clarification before proceeding.",
                        "confidence": 0.15,
                        "violations": ["Conflicting decisions for caching."],
                        "suggestions": ["Clarify whether Redis or Memcached is the intended cache."],
                    }),
                    "error": None
                }
        
        # 3. WEAK SIGNAL: Expecting Flexibility
        if "WEAK SIGNAL" in prompt_upper or "LOW CONFIDENCE" in prompt_upper:
            if task_is_logging:
                return {
                    "ok": True,
                    "text": json.dumps({
                        "decision": "PASS",
                        "reason": "Considering file-based logging as a potential suggestion, not a strict requirement.",
                        "confidence": 0.55,
                        "suggestions": ["Use file-based logging if it fits the runtime environment."],
                    }),
                    "error": None
                }

        # Fallback to Task-aware defaults
        if task_is_logging:
            return {
                "ok": True,
                "text": json.dumps({
                    "decision": "PASS",
                    "reason": "Considering file-based logging as a potential suggestion, with sensitive data checks applied.",
                    "confidence": 0.6,
                }),
                "error": None,
            }
        if task_is_database:
            return {
                "ok": True,
                "text": json.dumps({
                    "decision": "PASS",
                    "reason": "Use SQLite as the mandated architectural invariant.",
                    "confidence": 0.95,
                }),
                "error": None,
            }
        
        return {
            "ok": True,
            "text": json.dumps({
                "decision": "PASS",
                "reason": "Task processed successfully by semantic mock.",
                "confidence": 0.7,
            }),
            "error": None
        }
