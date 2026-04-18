import time

from kit.core.metrics import ModelMetrics
from kit.core.router import ModelRouter


def test_router_skips_provider_in_active_cooldown() -> None:
    gemini = ModelMetrics(name="gemini", cost_per_1k=0.001, failures=2, healthy=False, last_updated=time.time(), last_error_type="CAPACITY")
    local = ModelMetrics(name="local", cost_per_1k=0.0)

    router = ModelRouter(models={"gemini": gemini, "local": local}, epsilon=0.0)

    assert router.select("general") == "local"


def test_router_falls_back_to_least_damaged_model_when_all_cooling_down() -> None:
    gemini = ModelMetrics(name="gemini", cost_per_1k=0.001, failures=4, healthy=False, last_updated=time.time(), last_error_type="CAPACITY")
    secondary = ModelMetrics(name="secondary", cost_per_1k=0.002, failures=2, healthy=False, last_updated=time.time(), last_error_type="CAPACITY")

    router = ModelRouter(models={"gemini": gemini, "secondary": secondary}, epsilon=0.0)

    assert router.select("general") == "secondary"
