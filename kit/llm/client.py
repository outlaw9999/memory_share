# kit/llm/client.py
from typing import Any, Dict, List, Optional

from kit.llm.circuit import CircuitBreaker


class LLMClient:
    def __init__(self, provider: Optional[Any] = None) -> None:
        self.provider = provider
        self.breaker = CircuitBreaker()

    def summarize_facts(self, facts: Dict[str, Any]) -> str:
        if not self.breaker.allow():
            raise RuntimeError("LLM circuit open")

        if not self.provider:
            # For now, just raise if no provider
            raise RuntimeError("No LLM provider configured")

        try:
            prompt = self._build_prompt(facts)
            result = self.provider.generate(prompt)
            self.breaker.success()
            return str(result)
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                self.breaker.failure()
            raise

    def _build_prompt(self, facts: Dict[str, Any]) -> str:
        lines: List[str] = []
        lines.append(f"Explain the role of {facts['name']} in the system.")
        lines.append("\nStructural relations:")
        for c in facts.get("callers", []):
            lines.append(f"- called by {c}")
        lines.append("\nDesign intent:")
        for a in facts.get("assertions", []):
            lines.append(f"- {a['text']}")
        return "\n".join(lines)
