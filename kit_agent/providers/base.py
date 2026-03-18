from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProvider(ABC):
    @abstractmethod
    def ask(self, prompt: str) -> Dict[str, Any]:
        """
        Return dict with:
        {
            "ok": bool,
            "text": str,
            "error": Optional[str]
        }
        """
        pass
