from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    @abstractmethod
    def ask(self, prompt: str) -> dict[str, Any]:
        """
        Return dict with:
        {
            "ok": bool,
            "text": str,
            "error": Optional[str]
        }
        """
        pass
