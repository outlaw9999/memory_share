from typing import Any

import pytest
import requests

from kit.providers.local import LocalLLMProvider


class DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


def test_local_provider_normalizes_v1_suffix() -> None:
    provider = LocalLLMProvider(base_url="http://127.0.0.1:1337")
    assert provider.base_url == "http://127.0.0.1:1337/v1"


def test_local_provider_preserves_existing_v1_suffix() -> None:
    provider = LocalLLMProvider(base_url="http://127.0.0.1:1337/v1")
    assert provider.base_url == "http://127.0.0.1:1337/v1"


def test_local_provider_ask_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], headers: dict[str, str], timeout: float) -> DummyResponse:
        captured["post_url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["post_timeout"] = timeout
        return DummyResponse(
            200,
            payload={"choices": [{"message": {"content": "local answer"}}]},
        )

    def fake_get(url: str, timeout: float, headers: dict[str, str]) -> DummyResponse:
        captured["get_url"] = url
        return DummyResponse(200, payload={"data": [{"id": "jan-test"}]})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    provider = LocalLLMProvider(base_url="http://127.0.0.1:1337", model_id="jan-test")
    result = provider.ask("hello Jan")

    assert result == {"ok": True, "text": "local answer", "error": None, "error_type": None}
    assert captured["post_url"] == "http://127.0.0.1:1337/v1/chat/completions"
    assert captured["json"]["model"] == "jan-test"
    assert captured["post_timeout"] == 30.0


def test_local_provider_connection_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any], headers: dict[str, str], timeout: float) -> DummyResponse:
        raise requests.exceptions.ConnectionError("[WinError 10061] Connection refused")

    def fake_get(url: str, timeout: float, headers: dict[str, str]) -> DummyResponse:
        return DummyResponse(200, payload={"data": [{"id": "phi-3-mini:latest"}]})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    provider = LocalLLMProvider()
    result = provider.ask("hello Jan")

    assert result["ok"] is False
    assert "LOCAL_LLM_NETWORK" in result["error"]
    assert "Connection refused" in result["error"]


def test_local_provider_is_alive_uses_models_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_get(url: str, timeout: float, headers: dict[str, str]) -> DummyResponse:
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        return DummyResponse(200, payload={"data": [{"id": "active-model"}]})

    monkeypatch.setattr(requests, "get", fake_get)

    # Note: is_alive() will call GET /models twice if it triggers _ensure_model_id
    provider = LocalLLMProvider(timeout=9.0)
    assert provider.is_alive() is True
    assert captured["url"] == "http://127.0.0.1:1337/v1/models"
    assert captured["timeout"] == 5.0
