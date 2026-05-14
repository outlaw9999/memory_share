# kit/intent/registry.py
# v1.2.5 — Intent Registry: maps CanonicalIntent → HandlerDescriptor (capability-based).

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kit.intent.schema import CanonicalIntent, IntentPayload, IntentResult, RuntimeTrace, TraceStatus

logger = logging.getLogger("kit.intent.registry")


@runtime_checkable
class IntentHandler(Protocol):
    """Protocol for any callable that handles a canonical intent."""
    def __call__(self, payload: IntentPayload) -> IntentResult: ...


@dataclass
class HandlerDescriptor:
    """
    Execution capability descriptor — richer than a bare callable.
    Enables the runtime to make decisions about retries, verification, async dispatch, etc.
    """
    handler: Callable[[IntentPayload], IntentResult]
    side_effects: bool = True
    retryable: bool = False
    requires_verification: bool = False
    async_capable: bool = False
    timeout_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class IntentRegistry:
    """
    Central registry mapping CanonicalIntent → HandlerDescriptor.
    One handler per intent. Registration replaces previous handler.
    """

    def __init__(self):
        self._descriptors: dict[CanonicalIntent, HandlerDescriptor] = {}

    def register(self, intent: CanonicalIntent,
                 handler: Callable[[IntentPayload], IntentResult],
                 descriptor: HandlerDescriptor | None = None) -> None:
        if not isinstance(intent, CanonicalIntent):
            raise TypeError(f"Expected CanonicalIntent, got {type(intent).__name__}")
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler).__name__}")
        if descriptor is None:
            descriptor = HandlerDescriptor(handler=handler)
        else:
            descriptor.handler = handler
        self._descriptors[intent] = descriptor
        logger.debug("Registered handler for %s", intent)

    def resolve(self, intent: CanonicalIntent) -> HandlerDescriptor | None:
        return self._descriptors.get(intent)

    def dispatch(self, payload: IntentPayload) -> IntentResult:
        descriptor = self.resolve(payload.intent)
        if descriptor is None:
            return IntentResult(
                intent=payload.intent,
                trace=RuntimeTrace.create(
                    trace_id=payload.context.trace_id,
                    intent_chain=[payload.intent],
                ),
                status=TraceStatus.FAILED,
                error=f"No handler registered for {payload.intent}",
            )
        return descriptor.handler(payload)

    @property
    def registered_intents(self) -> list[CanonicalIntent]:
        return list(self._descriptors.keys())

    def __contains__(self, intent: CanonicalIntent) -> bool:
        return intent in self._descriptors


registry: IntentRegistry = IntentRegistry()
