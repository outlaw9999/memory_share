import json
import os
from typing import Any

import requests
from requests import Response
from requests.exceptions import RequestException, Timeout

from kit_agent.providers.base import BaseProvider


class LocalLLMProvider(BaseProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://127.0.0.1:1337",
        model_id: str = "phi-3-mini:latest",
        timeout: float = 30.0,
    ) -> None:
        env_base_url = os.environ.get("JAN_BASE_URL") or os.environ.get("LOCAL_LLM_BASE_URL")
        env_api_key = os.environ.get("JAN_API_KEY") or os.environ.get("LOCAL_LLM_API_KEY")
        env_model_id = os.environ.get("JAN_MODEL_ID") or os.environ.get("LOCAL_LLM_MODEL_ID")

        # Normalize URL to include /v1
        raw_url = env_base_url or base_url
        self.base_url = raw_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"

        self.api_key = api_key or env_api_key or "jan-local"
        self.model_id = env_model_id or model_id
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _discover_model_id(self) -> str | None:
        """Queries Jan for active models and returns the most suitable ID."""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                timeout=5.0,
                headers=self._headers(),
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                if models:
                    # Sort by ID descending to pick newer/larger models if multiple present
                    discovered_id = sorted(models, key=lambda x: x["id"], reverse=True)[0]["id"]
                    print(f"\033[90m[INFO] [LOCAL] Auto-discovered model: {discovered_id}\033[0m")
                    return discovered_id
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            pass
        return None

    def _ensure_model_id(self) -> None:
        """Ensures self.model_id is valid: auto-discover if placeholder or likely broken."""
        placeholder_ids = ["phi-3-mini:latest", "jan-v3-4b", "default", "", None]

        # We also trigger discovery if the ID contains '\' (typical for raw Jan IDs that might have changed)
        # or if JAN_AUTO_DISCOVER is explicitly enabled.
        should_discover = (
            self.model_id in placeholder_ids or "\\" in str(self.model_id) or os.environ.get("JAN_AUTO_DISCOVER") == "1"
        )

        if should_discover:
            discovered = self._discover_model_id()
            if discovered:
                self.model_id = discovered
            else:
                if self.model_id == "phi-3-mini:latest":
                    print("\033[93m[WARN] [LOCAL] Auto-discovery failed. Blindly using fallback.\033[0m")

    def ask(self, prompt: str) -> dict[str, Any]:
        """Generate a response from the local LLM via a Jan-compatible API."""
        self._ensure_model_id()

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            return self._parse_chat_response(response)
        except RequestException as error:
            error_type = "TIMEOUT" if isinstance(error, Timeout) else "NETWORK"
            return {"ok": False, "error": f"LOCAL_LLM_{error_type}: {error}", "text": "", "error_type": error_type}

    def _parse_chat_response(self, response: Response) -> dict[str, Any]:
        if response.status_code != 200:
            # If we get a Model Not Found, reset for next time's discovery
            if response.status_code == 404:
                print(f"\033[91m[WARN] [LOCAL] Model {self.model_id} not found in Jan.\033[0m")
                self.model_id = "phi-3-mini:latest"  # Force re-discovery next time
                return {
                    "ok": False,
                    "error": response.text,
                    "text": "",
                    "error_type": "CAPACITY",
                }  # Trigger circuit breaker
            return {
                "ok": False,
                "error": f"LOCAL_LLM_HTTP_{response.status_code}: {response.text}",
                "text": "",
                "error_type": "HTTP",
            }

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return {"ok": True, "text": content, "error": None, "error_type": None}
        except (KeyError, IndexError, TypeError, ValueError) as error:
            return {
                "ok": False,
                "error": f"LOCAL_LLM_BAD_RESPONSE: {error}",
                "text": "",
                "error_type": "BAD_RESPONSE",
            }

    def is_alive(self) -> bool:
        """Check if Jan API is reachable and proactive discover models."""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                timeout=5.0,
                headers=self._headers(),
            )
            if response.status_code == 200:
                self._ensure_model_id()
                return True
        except RequestException:
            pass
        return False
