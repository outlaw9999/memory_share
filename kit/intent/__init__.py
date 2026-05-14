# kit/intent/__init__.py
# v1.2.5 — Intent Layer: Canonical semantic surface for the KIT system.

from kit.intent.execution import ExecutionIntent, ExecutionSource, Mutability
from kit.intent.normalizer import (
    normalize_agent_signal,
    normalize_git_event,
    normalize_manual,
)
from kit.intent.registry import HandlerDescriptor, IntentHandler, IntentRegistry, registry
from kit.intent.schema import (
    CanonicalIntent,
    ExecutionLineage,
    IntentAction,
    IntentContext,
    IntentDomain,
    IntentOrigin,
    IntentPayload,
    IntentResult,
    MutationLog,
    MutationRecord,
    ObservationLog,
    RuntimeTrace,
    TimestampRecord,
    TraceMetadata,
    TraceStatus,
    VerdictLog,
    VerdictRecord,
)

__all__ = [
    "CanonicalIntent",
    "IntentDomain",
    "IntentAction",
    "IntentContext",
    "IntentOrigin",
    "IntentPayload",
    "IntentResult",
    "RuntimeTrace",
    "TraceStatus",
    "TraceMetadata",
    "ExecutionLineage",
    "MutationLog",
    "MutationRecord",
    "ObservationLog",
    "TimestampRecord",
    "VerdictLog",
    "VerdictRecord",
    "ExecutionIntent",
    "ExecutionSource",
    "Mutability",
    "normalize_git_event",
    "normalize_agent_signal",
    "normalize_manual",
    "IntentHandler",
    "HandlerDescriptor",
    "IntentRegistry",
    "registry",
]
