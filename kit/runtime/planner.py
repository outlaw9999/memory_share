# kit/runtime/planner.py
# v1.2.5 — Planner: pure DAG construction, zero side effects.
# INVARIANT: ExecutionPlan is frozen — never mutated after creation.

import uuid
from dataclasses import dataclass, field
from typing import Any

from kit.intent.execution import ExecutionIntent, Mutability
from kit.intent.schema import CanonicalIntent, IntentContext
from kit.runtime.resolver import ResolverResult


@dataclass(frozen=True, order=True)
class ExecutionStep:
    """A single node in the execution DAG. Immutable after construction."""
    order: int
    action: str
    handler_ref: str
    mutability: Mutability
    input_data: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[int, ...] = ()


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Complete execution DAG. Immutable — no mutation after creation.
    Guarantees replayability and deterministic execution.
    """
    intent: CanonicalIntent
    steps: tuple[ExecutionStep, ...]
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of executing one step. Not frozen — populated during execution."""
    step: ExecutionStep
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class Planner:
    """Constructs ExecutionPlan from ResolverResult. Pure function — no state mutation."""

    @staticmethod
    def plan(resolved: ResolverResult, context: IntentContext) -> ExecutionPlan:
        step = ExecutionStep(
            order=0,
            action=str(resolved.intent),
            handler_ref=resolved.domain,
            mutability=resolved.mutability,
            input_data={},
        )
        return ExecutionPlan(
            intent=resolved.intent,
            steps=(step,),
        )
