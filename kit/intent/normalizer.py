# kit/intent/normalizer.py
# v1.2.5 — Intent Normalizer: git events / agent signals / manual input → canonical intents.
# Security invariant: the normalizer is the trust boundary — ALL external input must pass through it.

import os
import re

from kit.intent.schema import (
    CanonicalIntent,
    IntentAction,
    IntentContext,
    IntentDomain,
    IntentOrigin,
    IntentPayload,
)

GIT_EVENT_MAP: dict[str, CanonicalIntent] = {
    "pre-commit": CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT),
    "post-commit": CanonicalIntent(IntentDomain.LIFECYCLE, IntentAction.POST_COMMIT),
    "post-merge": CanonicalIntent(IntentDomain.MEMORY, IntentAction.RECONCILE),
    "pre-push": CanonicalIntent(IntentDomain.VERIFICATION, IntentAction.VALIDATE),
}

_ALLOWED_GIT_EVENTS: frozenset = frozenset(GIT_EVENT_MAP)

AGENT_INTENT_PATTERN = re.compile(r"INTENT:\s*(\w+)(?::(\w+))?")
# Security: restrict agent signals to alphanumeric + colon + whitespace
_ALLOWED_SIGNAL_CHARS: re.Pattern = re.compile(r"^[A-Za-z0-9\s:]+$")
_MAX_SIGNAL_LENGTH: int = 128
_MAX_EVENT_LENGTH: int = 64


def _validate_input(raw: str, max_len: int, context: str) -> str:
    """Sanitize and validate external input at the trust boundary."""
    if not raw or not raw.strip():
        raise ValueError(f"Empty {context} input rejected at trust boundary")
    if len(raw) > max_len:
        raise ValueError(f"{context} input exceeds max length ({len(raw)} > {max_len})")
    return raw.strip()


def normalize_git_event(event: str, **kwargs) -> IntentPayload:
    """Convert a git hook event name to a full IntentPayload."""
    event = _validate_input(event, _MAX_EVENT_LENGTH, "git event")
    if event not in _ALLOWED_GIT_EVENTS:
        raise ValueError(f"Unknown git event: {event!r}. Allowed: {sorted(_ALLOWED_GIT_EVENTS)}")

    canonical = GIT_EVENT_MAP[event]

    branch = kwargs.get("branch") or os.environ.get("GIT_BRANCH", "")
    commit_hash = kwargs.get("commit_hash") or os.environ.get("GIT_COMMIT", "")
    git_diff = kwargs.get("git_diff", "")

    ctx = IntentContext(
        caller_id=f"git:{event}",
        origin=IntentOrigin.HOOK,
        execution_depth=_detect_depth(),
    )

    data = {"git_event": event, "hook_type": event}
    if git_diff:
        data["diff_size"] = len(git_diff)

    return IntentPayload(
        intent=canonical,
        context=ctx,
        data=data,
        git_diff=git_diff or None,
        branch=branch or None,
        commit_hash=commit_hash or None,
    )


def normalize_agent_signal(signal: str, **kwargs) -> IntentPayload:
    """Convert a raw agent signal string (e.g. 'INTENT: MEMORY:LEARN') to IntentPayload.
    Security: validates input at trust boundary — rejects malformed or oversized signals."""
    signal = _validate_input(signal, _MAX_SIGNAL_LENGTH, "agent signal")
    if not _ALLOWED_SIGNAL_CHARS.match(signal):
        raise ValueError(f"Agent signal contains disallowed characters: {signal!r}")

    match = AGENT_INTENT_PATTERN.match(signal)
    if not match:
        raise ValueError(f"Unrecognized agent signal format: {signal!r}")

    raw_domain = match.group(1)
    raw_action = match.group(2)

    if raw_action:
        canonical = CanonicalIntent(
            domain=IntentDomain(raw_domain.lower()),
            action=IntentAction(raw_action.lower()),
        )
    else:
        canonical = _legacy_single_token(raw_domain)

    ctx = IntentContext(
        caller_id=f"agent:{kwargs.get('agent_id', 'unknown')}",
        origin=IntentOrigin.AGENT,
        execution_depth=_detect_depth(),
    )

    return IntentPayload(
        intent=canonical,
        context=ctx,
        data=kwargs,
    )


def normalize_manual(intent_str: str, **kwargs) -> IntentPayload:
    """Convert a user-specified 'DOMAIN:ACTION' string to IntentPayload (debug/inspect mode)."""
    canonical = CanonicalIntent.from_string(intent_str)

    ctx = IntentContext(
        caller_id=kwargs.pop("caller_id", "manual:user"),
        origin=IntentOrigin.MANUAL,
        execution_depth=_detect_depth(),
    )

    return IntentPayload(intent=canonical, context=ctx, data=kwargs)


def _legacy_single_token(token: str) -> CanonicalIntent:
    """Heuristic mapping for old single-token intents (backward compat with AGENTS.md IR-C1)."""
    mapping = {
        "BUILD": (IntentDomain.GRAPH, IntentAction.BUILD),
        "TEST": (IntentDomain.RELEASE, IntentAction.TEST),
        "VERIFY": (IntentDomain.VERIFICATION, IntentAction.VERIFY),
        "HEALTH": (IntentDomain.RUNTIME, IntentAction.HEALTH),
        "HEALTH_CHECK": (IntentDomain.RUNTIME, IntentAction.HEALTH),
        "MIGRATE": (IntentDomain.MEMORY, IntentAction.MIGRATE),
        "RELEASE": (IntentDomain.RELEASE, IntentAction.RELEASE),
        "LEARN": (IntentDomain.MEMORY, IntentAction.LEARN),
        "RECALL": (IntentDomain.MEMORY, IntentAction.RECALL),
        "INTROSPECT": (IntentDomain.RUNTIME, IntentAction.INTROSPECT),
        "COMMIT": (IntentDomain.LIFECYCLE, IntentAction.COMMIT),
        "RECONCILE": (IntentDomain.MEMORY, IntentAction.RECONCILE),
        "PRE_COMMIT": (IntentDomain.LIFECYCLE, IntentAction.PRE_COMMIT),
        "POST_COMMIT": (IntentDomain.LIFECYCLE, IntentAction.POST_COMMIT),
        "DOCTOR": (IntentDomain.DIAGNOSTIC, IntentAction.DOCTOR),
    }
    domain, action = mapping.get(
        token.upper(),
        (IntentDomain.RUNTIME, IntentAction.EXECUTE),
    )
    return CanonicalIntent(domain=domain, action=action)


def _detect_depth() -> int:
    """Read KIT_EXECUTION_DEPTH from env, return parsed int (default 0)."""
    raw = os.environ.get("KIT_EXECUTION_DEPTH", "0")
    try:
        return max(0, int(raw))
    except (ValueError, TypeError):
        return 0
