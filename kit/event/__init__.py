# kit/event/__init__.py
# v1.2.5 — Event Contract: formal boundary between Plane 1 (Git) and Plane 2 (Runtime).

from kit.event.contract import (
    CONTRACT_VERSION,
    EventContractError,
    RawGitEvent,
    RawGitEventOrigin,
    RawGitEventPayload,
    idempotency_key,
)

__all__ = [
    "CONTRACT_VERSION",
    "EventContractError",
    "RawGitEvent",
    "RawGitEventPayload",
    "RawGitEventOrigin",
    "idempotency_key",
]
