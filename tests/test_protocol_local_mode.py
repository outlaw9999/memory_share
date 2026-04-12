import json
import time
from dataclasses import dataclass
from typing import Any

import pytest

from kit_agent.core.cache import SemanticCache
from kit_agent.core.metrics import ModelMetrics
from kit_agent.core.protocol import AMSBProtocol


class StubProvider:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses

    def ask(self, prompt: str) -> dict[str, Any]:
        return self._responses.pop(0)


class StubRouter:
    def __init__(self, selections: list[str]) -> None:
        self._selections = selections
        self.models = {
            "gemini": ModelMetrics(name="gemini", cost_per_1k=0.001),
            "local": ModelMetrics(name="local", cost_per_1k=0.0),
        }

    def select(self, task_type: str = "general") -> str:
        return self._selections.pop(0)

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
def disable_search_fallback(monkeypatch) -> None:
    monkeypatch.setattr("kit_agent.core.protocol.kit_api.search", lambda *args, **kwargs: [])


def test_protocol_labels_local_mode_on_success(monkeypatch) -> None:
    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(memories=[FakeMemory("context")], confidence=1.0, status="HIGH_CONFIDENCE"),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["local"]),
        providers={"local": StubProvider([{"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"jan response\",\"confidence\":0.9}", "error": None}])},
        cache=SemanticCache(),
    )

    result = protocol.run("say hello")

    payload = json.loads(result)
    assert payload["provider"] == "local"
    assert payload["decision"] == "PASS"
    assert payload["reason"] == "jan response"


def test_protocol_labels_local_mode_after_fallback(monkeypatch) -> None:
    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(memories=[FakeMemory("context")], confidence=1.0, status="HIGH_CONFIDENCE"),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["gemini", "local"]),
        providers={
            "gemini": StubProvider([{"ok": False, "text": "", "error": "503_CAPACITY_EXHAUSTED", "error_type": "CAPACITY"}]),
            "local": StubProvider([{"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"fallback answer\",\"confidence\":0.8}", "error": None, "error_type": None}]),
        },
        cache=SemanticCache(),
    )

    result = protocol.run("write cache function")

    payload = json.loads(result)
    assert payload["provider"] == "local"
    assert payload["decision"] == "PASS"
    assert payload["reason"] == "fallback answer"


def test_protocol_capacity_failure_marks_provider_down_without_delay(monkeypatch) -> None:
    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(memories=[], confidence=0.0, status="EMPTY"),
    )

    router = StubRouter(["gemini", "local"])
    protocol = AMSBProtocol(
        router=router,
        providers={
            "gemini": StubProvider([{"ok": False, "text": "", "error": "503_CAPACITY_EXHAUSTED", "error_type": "CAPACITY"}]),
            "local": StubProvider([{"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"fallback answer\",\"confidence\":0.8}", "error": None, "error_type": None}]),
        },
        cache=SemanticCache(),
    )

    start = time.perf_counter()
    result = protocol.run("write cache function")
    duration = time.perf_counter() - start

    payload = json.loads(result)
    assert payload["provider"] == "local"
    assert payload["decision"] == "PASS"
    assert payload["reason"] == "fallback answer"
    assert duration < 0.5
    assert router.models["gemini"].healthy is False
    assert router.models["gemini"].cooldown_active() is True


def test_protocol_injects_memory_block_into_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    class CapturingProvider:
        def ask(self, prompt: str) -> dict[str, Any]:
            captured["prompt"] = prompt
            return {"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"done\",\"confidence\":0.8}", "error": None}

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(
            memories=[
                FakeMemory("NEVER use Redis for caching because it breaks determinism"),
                FakeMemory("Use SQLite"),
            ],
            confidence=0.9,
            status="HIGH_CONFIDENCE",
        ),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["gemini"]),
        providers={"gemini": CapturingProvider()},
        cache=SemanticCache(),
    )

    protocol.run("design cache invalidation")

    assert "[MEMORY RULES]\n- NEVER use Redis for caching because it breaks determinism\n- Use SQLite" in captured["prompt"]
    assert "\n\n[TASK]\ndesign cache invalidation" in captured["prompt"]


def test_protocol_handles_empty_memory_without_crashing(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    class CapturingProvider:
        def ask(self, prompt: str) -> dict[str, Any]:
            captured["prompt"] = prompt
            return {"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"done\",\"confidence\":0.8}", "error": None}

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(memories=[], confidence=0.0, status="EMPTY"),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["local"]),
        providers={"local": CapturingProvider()},
        cache=SemanticCache(),
    )

    result = protocol.run("check empty memory")

    payload = json.loads(result)
    assert payload["provider"] == "local"
    assert payload["decision"] == "PASS"
    assert payload["reason"] == "done"
    assert "[STRICT EXECUTION RULES]" in captured["prompt"]
    assert "[OUTPUT CONTRACT]" in captured["prompt"]
    assert captured["prompt"].endswith("[TASK]\ncheck empty memory")


def test_protocol_limits_and_truncates_memory_rules(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    class CapturingProvider:
        def ask(self, prompt: str) -> dict[str, Any]:
            captured["prompt"] = prompt
            return {"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"done\",\"confidence\":0.8}", "error": None}

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(
            memories=[
                FakeMemory("This is a very long memory line that should be truncated aggressively before it reaches the prompt for the local model"),
                FakeMemory("Use SQLite for cache state"),
                FakeMemory("Token skew tolerance is 30 seconds"),
                FakeMemory("This fourth line should never appear"),
            ],
            confidence=0.8,
            status="HIGH_CONFIDENCE",
        ),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["gemini"]),
        providers={"gemini": CapturingProvider()},
        cache=SemanticCache(),
    )

    protocol.run("validate tokens")

    assert "This fourth line should never appear" not in captured["prompt"]
    assert "This is a very long memory line that should be truncated aggressively before it" in captured["prompt"]


def test_protocol_marks_ambiguous_memory_in_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    class CapturingProvider:
        def ask(self, prompt: str) -> dict[str, Any]:
            captured["prompt"] = prompt
            return {"ok": True, "text": "{\"decision\":\"WARN\",\"reason\":\"depends\",\"confidence\":0.2}", "error": None}

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(
            memories=[FakeMemory("Use SQLite"), FakeMemory("Use Redis")],
            confidence=0.05,
            status="AMBIGUOUS",
        ),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["gemini"]),
        providers={"gemini": CapturingProvider()},
        cache=SemanticCache(),
    )

    protocol.run("design cache system")

    assert "[MEMORY RULES - AMBIGUOUS]" in captured["prompt"]
    assert "CRITICAL: CONFLICT DETECTED IN ARCHITECTURAL SIGNALS" in captured["prompt"]
    assert "MUST NOT make a silent assumption" in captured["prompt"]
    assert "request clarification" in captured["prompt"]


def test_protocol_retries_when_provider_breaks_output_contract(monkeypatch) -> None:
    def fake_safe_run(command: list[str], input_text: str | None = None) -> tuple[str, str, int]:
        if "preflight" in command:
            return ("PASS", "", 0)
        if "learn" in command:
            return ("", "", 0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("kit_agent.core.protocol.safe_run", fake_safe_run)
    monkeypatch.setattr(
        "kit_agent.core.protocol.kit_api.recall_with_assessment",
        lambda *args, **kwargs: FakeAssessment(memories=[FakeMemory("Use SQLite")], confidence=1.0, status="HIGH_CONFIDENCE"),
    )

    protocol = AMSBProtocol(
        router=StubRouter(["gemini", "local"]),
        providers={
            "gemini": StubProvider([{"ok": True, "text": "not json", "error": None}]),
            "local": StubProvider([{"ok": True, "text": "{\"decision\":\"PASS\",\"reason\":\"fallback contract\",\"confidence\":0.8}", "error": None}]),
        },
        cache=SemanticCache(),
    )

    payload = json.loads(protocol.run("stabilize provider output"))
    assert payload["decision"] == "PASS"
    assert payload["provider"] == "local"
