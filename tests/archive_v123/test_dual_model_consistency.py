import json
from dataclasses import dataclass
from typing import Any

import pytest

from kit.core.cache import SemanticCache
from kit.core.metrics import ModelMetrics
from kit.core.protocol import AMSBProtocol
from kit.providers.gemini import GeminiProvider
from kit.providers.local import LocalLLMProvider


class StubRouter:
    def __init__(self) -> None:
        self.models = {
            "gemini": ModelMetrics(name="gemini", cost_per_1k=0.001),
            "local": ModelMetrics(name="local", cost_per_1k=0.0),
        }

    def select(self, task_type: str = "general") -> str:
        return "gemini"

    def update_model(
        self,
        name: str,
        success: bool,
        latency: float,
        error_type: str | None = None,
        is_block: bool = False,
    ) -> None:
        self.models[name] = self.models[name].with_update(
            success=success,
            latency=latency,
            error_type=error_type,
            is_block=is_block,
        )


@dataclass
class FakeMemory:
    content: str


@dataclass
class FakeAssessment:
    memories: list[FakeMemory]
    confidence: float
    status: str


@pytest.fixture(autouse=True)
def no_learn_side_effects(monkeypatch) -> None:
    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr("kit_agent.core.protocol.kit_api.search", lambda *args, **kwargs: [])


def _run_case(monkeypatch, assessment: FakeAssessment, gemini_text: str, local_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: assessment,
    )

    gemini = GeminiProvider(cli_path="gemini")
    local = LocalLLMProvider()

    monkeypatch.setattr(
        gemini,
        "ask",
        lambda prompt: {"ok": True, "text": gemini_text, "error": None, "error_type": None},
    )
    monkeypatch.setattr(
        local,
        "ask",
        lambda prompt: {"ok": True, "text": local_text, "error": None, "error_type": None},
    )

    gemini_protocol = AMSBProtocol(
        router=StubRouter(),
        providers={"gemini": gemini, "local": local},
        cache=SemanticCache(),
    )
    local_protocol = AMSBProtocol(
        router=StubRouter(),
        providers={"gemini": gemini, "local": local},
        cache=SemanticCache(),
    )

    gemini_result = json.loads(gemini_protocol.run("evaluate architectural task", forced_provider="gemini"))
    local_result = json.loads(local_protocol.run("evaluate architectural task", forced_provider="local"))
    return gemini_result, local_result


def test_dual_model_consistency_for_block(monkeypatch) -> None:
    assessment = FakeAssessment(
        memories=[FakeMemory("Auth must use JWT.")],
        confidence=0.98,
        status="HIGH_CONFIDENCE",
    )
    gemini_result, local_result = _run_case(
        monkeypatch,
        assessment,
        '{"decision":"BLOCK","reason":"JWT only invariant blocks cookies.","confidence":0.99}',
        '{"decision":"BLOCK","reason":"Cookies violate the JWT-only invariant.","confidence":0.97}',
    )
    assert gemini_result["decision"] == local_result["decision"] == "BLOCK"


def test_dual_model_consistency_for_warn(monkeypatch) -> None:
    assessment = FakeAssessment(
        memories=[FakeMemory("Use Redis"), FakeMemory("Use Memcached")],
        confidence=0.1,
        status="AMBIGUOUS",
    )
    gemini_result, local_result = _run_case(
        monkeypatch,
        assessment,
        '{"decision":"WARN","reason":"Redis and Memcached conflict; clarification required.","confidence":0.2}',
        '{"decision":"WARN","reason":"Caching decision is ambiguous and needs clarification.","confidence":0.18}',
    )
    assert gemini_result["decision"] == local_result["decision"] == "WARN"


def test_dual_model_consistency_for_pass(monkeypatch) -> None:
    assessment = FakeAssessment(
        memories=[FakeMemory("Use SQLite")],
        confidence=0.95,
        status="HIGH_CONFIDENCE",
    )
    gemini_result, local_result = _run_case(
        monkeypatch,
        assessment,
        '{"decision":"PASS","reason":"SQLite is the approved database choice.","confidence":0.96}',
        '{"decision":"PASS","reason":"Proceed with SQLite as approved.","confidence":0.94}',
    )
    assert gemini_result["decision"] == local_result["decision"] == "PASS"
