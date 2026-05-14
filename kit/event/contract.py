# kit/event/contract.py
# v1.2.5 — Event Contract: formal boundary between Plane 1 (Git) and Plane 2 (Runtime).
#
# PLANE 1 (Git hooks) produces → RawGitEvent JSON via stdout
# PLANE 2 (Runtime) consumes ← RawGitEvent JSON via stdin or --event flag
#
# INVARIANTS:
#   - Plane 1 never reads from Plane 2 (no reverse flow)
#   - Plane 2 never writes to Git (runtime is read-only at boundary)
#   - Idempotent: same (event, commit_hash) within 5s = no-op

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Optional

CONTRACT_VERSION = "1.0"


class EventContractError(Exception):
    """Raised when a RawGitEvent violates the contract."""


@dataclass
class RawGitEventPayload:
    """Event-specific data carried across the boundary."""

    commit_hash: str | None = None
    branch: str | None = None
    diff: str | None = None


@dataclass
class RawGitEventOrigin:
    """Provenance of the event — never trusted by Plane 2 for business logic."""

    type: str = "git_hook"
    repo: str | None = None
    hook_depth: int = 0


@dataclass
class RawGitEvent:
    """
    The ONLY valid input to Plane 2 (Cognitive Substrate).
    Emitted by Plane 1 (Git hooks) as JSON via stdout.
    """

    version: str = CONTRACT_VERSION
    event: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: RawGitEventPayload = field(default_factory=RawGitEventPayload)
    origin: RawGitEventOrigin = field(default_factory=RawGitEventOrigin)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_json(cls, raw: str) -> RawGitEvent:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise EventContractError(f"Invalid JSON: {e}") from e

        if data.get("version") != CONTRACT_VERSION:
            raise EventContractError(
                f"Contract version mismatch: got {data.get('version')}, expected {CONTRACT_VERSION}"
            )
        if not data.get("event"):
            raise EventContractError("Missing 'event' field")

        payload_data = data.get("payload", {})
        origin_data = data.get("origin", {})

        return cls(
            version=data["version"],
            event=data["event"],
            timestamp=data.get("timestamp", ""),
            payload=RawGitEventPayload(
                commit_hash=payload_data.get("commit_hash"),
                branch=payload_data.get("branch"),
                diff=payload_data.get("diff"),
            ),
            origin=RawGitEventOrigin(
                type=origin_data.get("type", "git_hook"),
                repo=origin_data.get("repo"),
                hook_depth=origin_data.get("hook_depth", 0),
            ),
        )

    @classmethod
    def from_stdin(cls) -> RawGitEvent:
        """Read and parse a RawGitEvent from stdin (pipe from Plane 1)."""
        raw = sys.stdin.read()
        if not raw.strip():
            raise EventContractError("Empty stdin — no RawGitEvent received")
        return cls.from_json(raw)

    @classmethod
    def from_env(cls, event: str) -> RawGitEvent:
        """Construct a RawGitEvent from environment variables (legacy adapter)."""
        import os

        return cls(
            event=event,
            payload=RawGitEventPayload(
                commit_hash=os.environ.get("KIT_GIT_COMMIT"),
                branch=os.environ.get("KIT_GIT_BRANCH"),
                diff=os.environ.get("KIT_GIT_DIFF"),
            ),
            origin=RawGitEventOrigin(
                hook_depth=int(os.environ.get("KIT_HOOK_DEPTH", "0")),
            ),
        )


# ── Idempotency key ────────────────────────────────────────────────────────────
# Same (event, commit_hash) = same cognitive outcome. Used by PolicyGuard.


def idempotency_key(event: RawGitEvent) -> tuple:
    """Unique key for deduplication. Same key = same cognitive result expected."""
    return (
        event.event,
        event.payload.commit_hash or event.timestamp,
    )
