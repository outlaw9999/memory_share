"""Bounded drift repair planning for cross-layer consistency."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from kit.core import execution_trace
from kit.core.consistency_validator import summarize_consistency


class DriftType(StrEnum):
    MECHANICAL = "mechanical"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"


class RepairRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RepairPlan(BaseModel):
    """Single bounded drift repair artifact."""

    model_config = ConfigDict(use_enum_values=True)

    drift_id: str
    type: DriftType
    source: str
    before: str
    after: str
    patch: str
    before_hash: str
    after_hash: str
    risk: RepairRisk
    requires_human: bool
    replayable: bool


class RepairPlanDocument(BaseModel):
    """Top-level repair plan document."""

    model_config = ConfigDict(use_enum_values=True)

    generated_at: str
    report_hash: str
    drifts: list[RepairPlan]


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _report_hash(report: dict[str, Any]) -> str:
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=True)
    return _sha256_text(canonical)


def _drift_id(kind: str, source: str, before_hash: str, after_hash: str) -> str:
    seed = f"{kind}|{source}|{before_hash}|{after_hash}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _line_number(text: str, needle: str) -> int:
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return 1


def _render_set_literal(commands: set[str]) -> str:
    ordered = ", ".join(f'"{item}"' for item in sorted(commands))
    return "{" + ordered + "}"


def _unified_diff(path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def _build_observability_plan(issue: dict[str, Any]) -> RepairPlan | None:
    overlap = set(issue.get("commands", []))
    if not overlap:
        return None

    file_path = Path(execution_trace.__file__).resolve()
    before_text = file_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^OBSERVABILITY_COMMANDS\s*=\s*(\{[^\n]+\})", re.MULTILINE)
    match = pattern.search(before_text)
    if not match:
        return None

    current_commands = set(execution_trace.OBSERVABILITY_COMMANDS)
    desired_commands = current_commands | overlap
    current_literal = match.group(1)
    desired_literal = _render_set_literal(desired_commands)
    after_text = before_text[: match.start(1)] + desired_literal + before_text[match.end(1) :]
    patch = _unified_diff(file_path, before_text, after_text)
    source_line = _line_number(before_text, "OBSERVABILITY_COMMANDS")
    before_hash = _sha256_text(before_text)
    after_hash = _sha256_text(after_text)

    return RepairPlan.model_validate(
        {
            "drift_id": _drift_id("observability_self_noise_overlap", f"{file_path}:{source_line}", before_hash, after_hash),
            "type": DriftType.MECHANICAL,
            "source": f"{file_path}:{source_line}",
            "before": current_literal,
            "after": desired_literal,
            "patch": patch,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "risk": RepairRisk.LOW,
            "requires_human": False,
            "replayable": True,
        }
    )


def _build_non_mutating_plan(
    *,
    kind: str,
    source: str,
    before: str,
    after: str,
    drift_type: DriftType,
    risk: RepairRisk,
    requires_human: bool = True,
) -> RepairPlan:
    before_hash = _sha256_text(before)
    after_hash = _sha256_text(after)
    return RepairPlan.model_validate(
        {
            "drift_id": _drift_id(kind, source, before_hash, after_hash),
            "type": drift_type,
            "source": source,
            "before": before,
            "after": after,
            "patch": "",
            "before_hash": before_hash,
            "after_hash": after_hash,
            "risk": risk,
            "requires_human": requires_human,
            "replayable": False,
        }
    )


def _issue_to_plan(issue: dict[str, Any]) -> RepairPlan | None:
    kind = str(issue.get("kind", "unknown"))

    if kind == "observability_self_noise_overlap":
        return _build_observability_plan(issue)

    if kind == "policy_runtime_reference":
        path = Path(__file__).resolve().parents[2] / "AGENTS.md"
        lines = issue.get("lines", [])
        return _build_non_mutating_plan(
            kind=kind,
            source=f"{path}:1",
            before="\n".join(lines),
            after="Remove runtime execution phrases from policy text and keep invariant-only constraints.",
            drift_type=DriftType.SEMANTIC,
            risk=RepairRisk.HIGH,
        )

    if kind == "missing_cli_surface":
        path = Path(__file__).resolve().parents[1] / "command_routes.py"
        commands = ", ".join(issue.get("commands", []))
        return _build_non_mutating_plan(
            kind=kind,
            source=f"{path}:1",
            before=f"Routed commands missing parser surface: {commands}",
            after="Add explicit parser entry or remove orphan route mapping.",
            drift_type=DriftType.STRUCTURAL,
            risk=RepairRisk.HIGH,
        )

    if kind == "missing_parser_fallback_handler":
        path = Path(__file__).resolve().parents[1] / "cli" / "main.py"
        commands = ", ".join(issue.get("commands", []))
        return _build_non_mutating_plan(
            kind=kind,
            source=f"{path}:1",
            before=f"Direct commands with option flags lack fallback handlers: {commands}",
            after="Register an explicit handler or move the command out of the direct fast path.",
            drift_type=DriftType.STRUCTURAL,
            risk=RepairRisk.MEDIUM,
        )

    if kind in {"unsupported_vantage_mapping", "direct_route_alias_drift"}:
        path = Path(__file__).resolve().parents[1] / "command_routes.py"
        items = issue.get("items", [])
        before = ", ".join(f"{item['command']}->{item.get('mapped_subcommand', '?')}" for item in items)
        after = "Align the route table with supported Vantage subcommands or remove the alias."
        return _build_non_mutating_plan(
            kind=kind,
            source=f"{path}:1",
            before=before,
            after=after,
            drift_type=DriftType.STRUCTURAL,
            risk=RepairRisk.MEDIUM,
        )

    return _build_non_mutating_plan(
        kind=kind,
        source=f"{Path(__file__).resolve()}:1",
        before=json.dumps(issue, sort_keys=True),
        after="Review this drift manually. No bounded repair strategy is registered.",
        drift_type=DriftType.SEMANTIC,
        risk=RepairRisk.HIGH,
    )


def build_repair_plan(consistency_report: dict[str, Any] | None = None) -> RepairPlanDocument:
    """Build a bounded repair plan from the current consistency report."""
    report = consistency_report or summarize_consistency()
    drifts = []
    for issue in report.get("issues", []):
        plan = _issue_to_plan(issue)
        if plan is not None:
            drifts.append(plan)

    return RepairPlanDocument.model_validate(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "report_hash": _report_hash(report),
            "drifts": [drift.model_dump(mode="json") for drift in drifts],
        }
    )


def validate_plan_document(payload: dict[str, Any]) -> RepairPlanDocument:
    """Validate a repair plan payload against the contract schema."""
    return RepairPlanDocument.model_validate(payload)


def validate_repair_mode(args: Any) -> str:
    """Ensure repair mode is explicit and singular."""
    selected = [
        name
        for name, enabled in {
            "plan": getattr(args, "plan", False),
            "diff": getattr(args, "diff", False),
            "apply": getattr(args, "apply", False),
            "symbol_debt": getattr(args, "symbol_debt", False),
        }.items()
        if enabled
    ]

    if len(selected) != 1:
        raise ValueError("Choose exactly one repair mode: --plan, --diff, --apply, or --symbol-debt.")
    return selected[0]


def repair_requires_kernel(args: Any) -> bool:
    """Return whether the chosen repair mode needs kernel initialization."""
    return getattr(args, "symbol_debt", False)


def render_repair_plan(plan_document: RepairPlanDocument) -> str:
    """Render a human-readable repair plan."""
    lines = [
        "DRIFT REPAIR PLAN",
        "=" * 40,
        f"Generated: {plan_document.generated_at}",
        f"Report Hash: {plan_document.report_hash}",
        f"Drifts: {len(plan_document.drifts)}",
    ]
    if not plan_document.drifts:
        lines.append("No drift candidates detected.")
        lines.append("=" * 40)
        return "\n".join(lines) + "\n"

    for drift in plan_document.drifts:
        lines.append(
            f"[{drift.type}] {drift.drift_id} risk={drift.risk} "
            f"human={'yes' if drift.requires_human else 'no'} replayable={'yes' if drift.replayable else 'no'}"
        )
        lines.append(f"  source: {drift.source}")
        lines.append(f"  before: {drift.before}")
        lines.append(f"  after:  {drift.after}")
    lines.append("=" * 40)
    return "\n".join(lines) + "\n"


def render_repair_diff(plan_document: RepairPlanDocument) -> str:
    """Render unified diff output for replayable mechanical drifts only."""
    patches = [
        drift.patch
        for drift in plan_document.drifts
        if drift.type == DriftType.MECHANICAL and drift.replayable and not drift.requires_human and drift.patch
    ]
    if not patches:
        return "No executable mechanical diffs generated.\n"
    return "\n".join(patches)


def apply_repair_plan(plan_document: RepairPlanDocument, confirm: bool) -> dict[str, Any]:
    """Guarded apply entry point. Mutation remains disabled in Repair Contract v1."""
    if not confirm:
        return {
            "status": "blocked",
            "reason": "confirmation_required",
            "applied": 0,
        }

    return {
        "status": "blocked",
        "reason": "apply_executor_disabled_in_v1",
        "applied": 0,
        "reviewable_diff": bool(render_repair_diff(plan_document).strip()),
    }


def validate_plan_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    """Helper for tests and command validation."""
    try:
        validate_plan_document(payload)
    except ValidationError as exc:
        return False, str(exc)
    return True, ""
