# kit/runtime/resolver.py
# v1.2.5 — Resolver: pure lookup from ExecutionIntent → ResolverResult.
# INVARIANT: No branching logic, no heuristics, no side effects.

from dataclasses import dataclass, field
from typing import Any

from kit.intent.execution import ExecutionIntent, ExecutionSource, Mutability
from kit.intent.registry import HandlerDescriptor, IntentRegistry
from kit.intent.schema import CanonicalIntent


@dataclass(frozen=True)
class ResolverResult:
    """Pure metadata — output of Resolver, input to Planner."""

    intent: CanonicalIntent
    handler_descriptor: HandlerDescriptor
    mutability: Mutability
    source: ExecutionSource
    domain: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Resolver:
    """Maps ExecutionIntent → ResolverResult via IntentRegistry. Pure lookup, zero branching."""

    def __init__(self, registry: IntentRegistry):
        self._registry = registry

    def resolve(self, execution_intent: ExecutionIntent) -> ResolverResult:
        intent = execution_intent.intent
        desc = self._registry.resolve(intent)
        if desc is None:
            raise ValueError(f"No handler registered for {intent}")
        return ResolverResult(
            intent=intent,
            handler_descriptor=desc,
            mutability=execution_intent.mutability,
            source=execution_intent.source,
            domain=intent.domain.value,
        )
