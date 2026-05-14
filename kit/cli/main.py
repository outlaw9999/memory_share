import argparse
import json
import logging
import os
import re
import shutil
import sys
import sysconfig
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Optional, Protocol, runtime_checkable

import yaml

from kit.core import kit_env
from kit.core.command_registry import CommandNamespace, CommandSideEffect, kit_command, registry
from kit.core.consistency_validator import summarize_consistency
from kit.core.drift_repair import (
    apply_repair_plan,
    build_repair_plan,
    render_repair_diff,
    render_repair_plan,
    repair_requires_kernel,
    validate_plan_payload,
    validate_repair_mode,
)
from kit.core.execution_trace import (
    log_execution_event,
    read_execution_events,
    summarize_execution_paths,
    summarize_hot_paths,
)
from kit.core.kit_baking import trigger_async_bake
from kit.core.kit_compaction import execute_compaction
from kit.core.kit_symbol_repair import repair_symbol_debt
from kit.core.policy_schema import LEARN_TAGS

# --- Section VII: Structured Logging (code-py-314) ---
logger = logging.getLogger("kit.cli")


@runtime_checkable
class DiagnosticPrinter(Protocol):
    """Protocol for diagnostic output reporting (v1.2.5)."""

    def __call__(self, msg: str, level: int = logging.INFO) -> None: ...


# --- CLI Constants (v1.2.5) ---
BOOTSTRAP_SENTINEL: Final[str] = ".kit/bootstrap_v1_2_5.seed"
INTERNAL_EPOCH: Final[str] = "1.2.5"
INTERNAL_DEV_VERSION: Final[str] = "1.2.5"


def get_cli_version() -> str:
    """Resolves the CLI version from distribution metadata with fallback to dev (AVS)."""
    import importlib.metadata

    try:
        return importlib.metadata.version("memory-share-kit")
    except importlib.metadata.PackageNotFoundError:
        return INTERNAL_DEV_VERSION


BOOTSTRAP_FACTS: Final[list[tuple[str, str]]] = [
    ("kit_startup", "kit startup begins with kit recall project_identity"),
    ("kit_rituals", "Daily: recall & verify. Weekly: hygiene & doctor. Monthly: seal."),
    ("flow_law", "Multi-step work MUST use 'kit flow run'. Isolation via transactions (v0.1.2)."),
    ("memory_law", "SQLite is Truth. observations.is_baked=1 is the only valid state for long-term memory."),
    ("arch_lighthouse", "AGENTS.md is the root contract; .kit/ is the private cognitive vault."),
    ("governance", "Maintain Entropy < 0.10. Run 'kit doctor --heal' to purge noise."),
    ("execution_contract", "All kit operations MUST route through 'kit' CLI (1.2.5)."),
]

# --- Console & Safety Helpers ---


def print_diagnostic(msg: str, level: int = logging.INFO) -> None:
    """Standard diagnostic output callback."""
    sys.stderr.write(f"{msg}\n")
    logger.log(level, msg)


def _configure_console_encoding() -> None:
    """Configures console encoding with explicit error boundaries (Rule II.1)."""
    if sys.platform != "win32":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, AttributeError) as e:
                # Rule II.1: No Silent Failures
                logger.warning(f"Console reconfiguration failed for {stream_name}: {e}")


def _cognitive_guardrail(text: str, tag: str | None) -> bool:
    """Detects 'logic smells' in cognitive ingestion (Rule V.2)."""
    smell_patterns = [
        r"\d+%",
        r"\d+ms",
        r"\d+s\s",
        r"\d+(KB|MB|GB|B)",
        r"cpu|ram|usage|load",
        r"error|exception",
        r"\d{4}-\d{2}-\d{2}",
    ]
    smell_keywords = {"currently", "now", "today", "recently", "temporary"}
    found_pattern = any(re.search(p, text, re.IGNORECASE) for p in smell_patterns)
    found_keyword = any(k in text.lower() for k in smell_keywords)
    if tag in ("invariant", "decision"):
        return found_pattern or found_keyword
    return False


def _bootloader_template() -> str:
    """Returns the canonical portable AGENTS.md template (v1.2.5)."""
    return (
        "# AGENTS.md\n\n"
        "- intents only\n"
        "- runtime is truth\n"
        "- no direct memory/db mutation\n"
        "- discover dynamically:\n"
        "  - `kit introspect --json`\n"
        "  - `kit <cmd> --help`\n"
        "- commit frequently\n"
    )


def _packaged_asset_root() -> Path | None:
    """Resolves the root path for packaged assets using Pathlib exclusively."""
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "docs" / "reference.md").exists():
        return source_root

    # Fallback to sysconfig data path
    data_path_str = sysconfig.get_path("data")
    if data_path_str:
        data_root = Path(data_path_str)
        shared_root = data_root / "share" / "memory_share_kit"
        return shared_root if shared_root.exists() else None
    return None


def _copy_if_missing(source_root: Path | None, relative_path: str, target_root: Path) -> bool:
    """Atomic copy helper using Pathlib (Rule I.1)."""
    if source_root is None:
        return False
    source_path = source_root / relative_path
    target_path = target_root / relative_path
    if not source_path.exists() or target_path.exists():
        return False

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        return True
    except OSError as e:
        logger.error(f"Failed to copy asset {relative_path}: {e}")
        return False


def _remove_if_exists(path: Path) -> bool:
    """Safe removal using Pathlib."""
    if not path.exists():
        return False
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except OSError as e:
        logger.warning(f"Could not remove {path}: {e}")
        return False


def _cleanup_empty_parent(path: Path, stop_at: Path) -> None:
    """Recursively removes empty parents up to a boundary."""
    current = path.parent
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _reset_managed_onboarding_files(root_path: Path, print_diagnostic: DiagnosticPrinter) -> None:
    """Purges managed cognitive artifacts."""
    legacy_paths = [root_path / "docs" / "reference.md", root_path / "scripts" / "kitf.ps1"]
    for path in legacy_paths:
        if path.exists():
            if _remove_if_exists(path):
                print_diagnostic(f"Cleaned legacy {path.name}")
                _cleanup_empty_parent(path, root_path)

    _remove_if_exists(root_path / "AGENTS.md")
    _remove_if_exists(root_path / ".kit")


def _materialize_onboarding_files(root_path: Path, print_diagnostic: DiagnosticPrinter) -> None:
    """Crystalizes the .kit cognitive substrate (v1.2.5)."""
    asset_root = _packaged_asset_root()
    kit_dir = root_path / ".kit"
    kit_dir.mkdir(parents=True, exist_ok=True)

    agents_md = root_path / "AGENTS.md"
    if not agents_md.exists():
        if not _copy_if_missing(asset_root, "AGENTS.md", root_path):
            agents_md.write_text(_bootloader_template(), encoding="utf-8")

    onboarding_files = ["scripts/kitf.ps1", "bootstrap_agent.yaml"]
    for rel_path in onboarding_files:
        _copy_if_missing(asset_root, rel_path, kit_dir if "scripts" in rel_path else root_path)

    # v1.2.5: Schema Loader external-first fallback
    kit_schema = kit_dir / "kit_schema.json"
    if not kit_schema.exists():
        fallback_schema = Path(__file__).resolve().parent.parent / "core" / "schema_default.json"
        if fallback_schema.exists():
            import shutil

            shutil.copyfile(fallback_schema, kit_schema)

    # v1.2.5: Materialize runtime metadata
    runtime_json = kit_dir / "runtime.json"
    if not runtime_json.exists():
        runtime_data = {
            "version": get_cli_version(),
            "epoch": INTERNAL_EPOCH,
            "initialized_at": datetime.now(UTC).isoformat(),
            "status": "sealed",
        }
        with open(runtime_json, "w", encoding="utf-8") as f:
            json.dump(runtime_data, f, indent=2)


def _seed_bootstrap_memories(root_path: Path, project_name: str) -> bool:
    """Seeds deterministic starter pack memories (Rule III.2)."""
    sentinel = root_path / BOOTSTRAP_SENTINEL
    if sentinel.exists():
        return False

    sentinel.write_text(f"seeded at {datetime.now(UTC)}\n", encoding="utf-8")

    import kit.api as api

    api.learn(
        uid="project_identity",
        content=f"Project '{project_name}' initialized and integrated into .kit cognitive system ({get_cli_version()}).",
        tag="decision",
        skip_render=True,
    )

    for uid, content in BOOTSTRAP_FACTS:
        # v1.2.5: Ensure each bootstrap fact has a unique UID and version provenance
        bootstrap_meta = {"version": "1.2.5", "source": "bootstrap"}
        api.learn(
            uid=uid, content=content, tag="decision", namespace="bootstrap", metadata=bootstrap_meta, skip_render=True
        )

    return True


# --- Command Registry Handlers (Strictly Typed) ---


@kit_command(
    name="init",
    namespace=CommandNamespace.CORE,
    description="Initialize a new .kit memory space",
    side_effect=CommandSideEffect.MUTATION,
)
def handle_init(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit init' command."""
    import kit.api as api
    from kit.api import resolve_paths

    _, project_db, root_path = resolve_paths(force_local=True)
    api.init_kernel(project_db, mode="isolated")

    # v1.2.5: Initialize graph schema (structure_edges + call_resolutions)
    from kit.core.memory_topology import MemoryTopology
    from kit.graph.schema import init_graph_db

    topology = MemoryTopology(project_root=root_path)
    conn = topology.connect("local", "local")
    init_graph_db(conn)
    conn.close()

    _materialize_onboarding_files(root_path, print_diagnostic)
    from kit.core.kit_sealing import seal_kernel

    seal_kernel(project_db)

    _seed_bootstrap_memories(root_path, root_path.name)

    # v1.2.5: Soft-check for Vantage availability
    import shutil

    if not (shutil.which("vantage") or shutil.which("kit-vantage")):
        print_diagnostic("\n⚠️ Vantage not detected. Verification features will be limited.")
        print_diagnostic("Install: https://github.com/so-sai/Vantage\n")

    print_diagnostic(f"[OK] Workspace initialized and sealed ({get_cli_version()}).")
    print("OK")

    # v1.2.5: Vantage Integrity Gating (Soft Check on Init)
    import subprocess

    from kit.core.kit_vantage import VANTAGE_BIN

    if VANTAGE_BIN and VANTAGE_BIN.exists() and os.getenv("KIT_DISABLE_ASYNC_BAKE") != "1":
        try:
            subprocess.run([str(VANTAGE_BIN), "verify-memory"], capture_output=True, timeout=5.0)
        except subprocess.TimeoutExpired:
            logger.warning("Vantage integrity check timed out during init.")

    print("OK")


@kit_command(
    name="init-env",
    namespace=CommandNamespace.CORE,
    description="Standardize VSCode and .env for relative path anchoring (v1.2.5)",
)
def handle_init_env(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Standardize project environment files."""
    root = Path.cwd()
    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)

    settings_path = vscode_dir / "settings.json"
    settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
        "python.terminal.useEnvFile": True,
        "python.analysis.extraPaths": ["${workspaceFolder}"],
        "terminal.integrated.env.windows": {"PYTHONPATH": "${workspaceFolder}"},
        "files.watcherExclude": {"**/.kit/**": True, "**/.pytest_cache/**": True},
    }
    import json

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    env_path = root / ".env"
    with open(env_path, "w") as f:
        f.write("PYTHONPATH=.\n")

    print_diagnostic(f"[OK] Environment standardized at {root}")
    print("OK")


@kit_command(
    name="learn",
    namespace=CommandNamespace.MEMORY,
    description="Ingest a new observation",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={
        "content": "string (or STDIN)",
        "tag": LEARN_TAGS,
        "namespace": "string (default: shared)",
        "importance": "float (0.0 - 1.0)",
        "symbol": "string (semantic node)",
    },
)
def handle_learn(
    args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, current_context: str = "shared", **kwargs: Any
) -> None:
    """Handler for 'kit learn' command."""
    from functools import partial

    import kit.api as api
    from kit.core.kernel_engine import DeterministicKernel
    from kit.core.kernel_fsm import ExecutionFrame
    from kit.core.kit_platform import FAST_TIMEOUT, read_stdin_fail_fast

    kernel = DeterministicKernel(session_id=os.getenv("KIT_SESSION_ID", "local-exec"))
    kernel.bind_brain(api.get_brain())

    content = getattr(args, "content", None) or read_stdin_fail_fast(timeout=FAST_TIMEOUT)
    if not content:
        print_diagnostic("Error: No content provided. (Use --content or pipe data via STDIN)")
        sys.exit(1)

    if _cognitive_guardrail(content, args.tag):
        print_diagnostic("[WARN] COGNITIVE FRICTION: Potential dynamic/volatile data detected.")

    import json

    metadata = {}
    if getattr(args, "metadata", None):
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print_diagnostic("Error: Invalid JSON in --metadata")
            sys.exit(1)

    action_call = partial(
        api.get_brain().learn,
        uid=getattr(args, "uid", None) or current_context,
        content=content,
        tag=args.tag,
        node_type=args.kind,
        importance=args.importance,
        namespace=getattr(args, "namespace", "shared"),
        symbol=getattr(args, "symbol", None),
        metadata=metadata,
    )

    frame = ExecutionFrame(action=action_call, command=f"learn:{getattr(args, 'uid', 'anonymous')}")
    kernel.submit(frame)

    if kernel.run():
        trigger_async_bake(api.get_brain())

        # v1.2.5: Mute narrative logs
        print("OK")
    else:
        # v1.2.5: Propagate semantic error code if present
        err_msg = frame.stderr or "Kernel execution failed during ingestion."
        if "KIT-SEALED" in err_msg:
            sys.stderr.write("KIT-SEALED: Run 'kit unseal --reason <msg>' to continue learning.\n")
            sys.exit(1)
        raise RuntimeError(err_msg)


@kit_command(
    name="recall",
    namespace=CommandNamespace.MEMORY,
    description="Recall ranked context (Project + Global)",
    input_schema={
        "entities": "list[string] (optional keywords)",
        "limit": "int (default: 15)",
        "query": "string (FTS search)",
        "here": "bool (limit to project scope)",
        "since": "relative date (e.g., 2d, 1h)",
    },
)
def handle_recall(
    args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, current_context: str = "shared", **kwargs: Any
) -> None:
    """Handler for 'kit recall' command."""
    import re
    from datetime import datetime, timedelta

    import kit.api as api

    def _parse_relative_date(val: str | None) -> str | None:
        if not val:
            return None
        match = re.match(r"(\d+)([dhm])", val.lower())
        if match:
            count, unit = int(match.group(1)), match.group(2)
            delta = (
                timedelta(days=count)
                if unit == "d"
                else (timedelta(hours=count) if unit == "h" else timedelta(minutes=count))
            )
            # 1.2.5patch: Format to SQLite compatible timestamp in UTC
            return (datetime.now(UTC) - delta).strftime("%Y-%m-%d %H:%M:%S")
        return val

    # 1.2.5patch: If no entities provided, pass None to enable Progressive Recall Fallback
    entities = args.entities if (hasattr(args, "entities") and args.entities) else None
    is_here = getattr(args, "here", False)

    memories = api.recall(
        entities,
        limit=getattr(args, "limit", 15),
        here=is_here,
        with_global=getattr(args, "with_global", False),
        query=getattr(args, "query", None),
        since=_parse_relative_date(getattr(args, "since", None)),
        until=_parse_relative_date(getattr(args, "until", None)),
    )

    if not memories:
        print_diagnostic("No context found.")
    else:
        for m in memories:
            # v1.2.5: Include UID for deterministic contract verification
            uid_str = f" [{m.node_uid}]" if hasattr(m, "node_uid") and m.node_uid else ""
            sys.stdout.write(f"* [{m.brain_source}:{m.tag}]{uid_str} {m.content}\n")


@kit_command(
    name="context", namespace=CommandNamespace.MEMORY, description="Alias for recall --here (Project context awareness)"
)
def handle_context(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit context' (alias for recall --here)."""
    args.here = True
    return handle_recall(args, print_diagnostic, **kwargs)


@kit_command(
    name="search",
    namespace=CommandNamespace.SEARCH,
    description="Hybrid FTS5 keyword search",
    input_schema={"query": "string (FTS query)", "limit": "int (default: 15)"},
)
def handle_search(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit search' command."""
    import kit.api as api

    query = getattr(args, "query", "")
    memories = api.search(query, limit=getattr(args, "limit", 15))

    if not memories:
        print_diagnostic(f"No matches found for '{query}'.")
    else:
        for m in memories:
            sys.stdout.write(f"* [ID:{m.id}][{m.brain_source}] {m.content}\n")


@kit_command(
    name="stats",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="Show AI Kernel health and Quality Index (GQI 2.0)",
    input_schema={
        "json": "bool (machine readable output)",
        "paths": "bool (execution path summary)",
        "hotpaths": "bool (executor-heavy command summary)",
        "limit": "int (telemetry sample size)",
    },
)
def handle_stats(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit stats' command (1.2.5STAGE5.1)."""
    if getattr(args, "consistency", False):
        import json as json_lib

        report = summarize_consistency()
        if getattr(args, "json", False):
            sys.stdout.write(json_lib.dumps(report, indent=2) + "\n")
            return

        sys.stdout.write("CROSS-LAYER CONSISTENCY\n")
        sys.stdout.write("=" * 40 + "\n")
        sys.stdout.write(f"Status: {'OK' if report.get('ok') else 'DRIFT'}\n")
        sys.stdout.write(f"Routes Checked: {report.get('routes_checked', 0)}\n")
        sys.stdout.write(f"Direct Fast Path: {', '.join(report.get('route_modes', {}).get('direct', [])) or 'none'}\n")
        overlap = report.get("observability", {}).get("self_noise_overlap", [])
        sys.stdout.write(f"Telemetry Self-Noise: {'clean' if not overlap else ', '.join(overlap)}\n")
        runtime_refs = report.get("policy", {}).get("runtime_references", [])
        sys.stdout.write(f"Policy Runtime Refs: {len(runtime_refs)}\n")

        for issue in report.get("issues", []):
            kind = issue.get("kind", "unknown")
            if "commands" in issue:
                detail = ", ".join(issue["commands"])
            elif "items" in issue:
                detail = ", ".join(
                    f"{item['command']}->{item.get('mapped_subcommand', '?')}" for item in issue["items"]
                )
            else:
                detail = "; ".join(issue.get("lines", []))
            sys.stdout.write(f"  [{kind}] {detail}\n")
        sys.stdout.write("=" * 40 + "\n")
        return

    if getattr(args, "hotpaths", False):
        import json as json_lib

        report = summarize_hot_paths(limit=getattr(args, "limit", 200))
        if getattr(args, "json", False):
            sys.stdout.write(json_lib.dumps(report, indent=2) + "\n")
            return

        sys.stdout.write("EXECUTION HOT PATHS\n")
        sys.stdout.write("=" * 40 + "\n")
        sys.stdout.write(f"Telemetry: {report.get('telemetry_path')}\n")
        sys.stdout.write(f"Sample Size: {report.get('sample_size', 0)} events\n")
        for item in report.get("hotpaths", [])[:10]:
            sys.stdout.write(
                f"{item['command']:12} band={item['cost_band']:6} "
                f"depth={item['reasoning_depth_ms']:7.3f}ms "
                f"exec={item['avg_executor_ms']:7.3f}ms "
                f"parser={item['avg_parser_ms']:7.3f}ms "
                f"n={item['event_count']:3} ok={item['success_rate']:.1%}\n"
            )
        sys.stdout.write("=" * 40 + "\n")
        return

    if getattr(args, "paths", False):
        import json as json_lib

        summary = summarize_execution_paths(limit=getattr(args, "limit", 200))
        if getattr(args, "json", False):
            sys.stdout.write(json_lib.dumps(summary, indent=2) + "\n")
            return

        sys.stdout.write("EXECUTION PATH COST SUMMARY\n")
        sys.stdout.write("=" * 40 + "\n")
        sys.stdout.write(f"Telemetry: {summary.get('telemetry_path')}\n")
        sys.stdout.write(f"Sample Size: {summary.get('sample_size', 0)} events\n")

        for mode, stages in summary.get("path_summary", {}).items():
            sys.stdout.write(f"\n{mode.upper()}:\n")
            for stage, metrics in stages.items():
                sys.stdout.write(
                    f"  {stage:8} count={metrics.get('count', 0):3} "
                    f"avg={metrics.get('avg_latency_ms', 0):7.3f}ms "
                    f"p95={metrics.get('p95_latency_ms', 0):7.3f}ms "
                    f"ok={metrics.get('success_rate', 0):.1%}\n"
                )

        fallbacks = summary.get("fallback_reasons", {})
        if fallbacks:
            sys.stdout.write("\nFALLBACKS:\n")
            for reason, count in sorted(fallbacks.items(), key=lambda item: (-item[1], item[0])):
                sys.stdout.write(f"  {reason:24} {count}\n")

        commands = summary.get("top_commands", [])
        if commands:
            sys.stdout.write("\nTOP COMMANDS:\n")
            for item in commands:
                sys.stdout.write(
                    f"  {item['command']:12} count={item['count']:3} "
                    f"avg={item['avg_latency_ms']:7.3f}ms ok={item['success_rate']:.1%}\n"
                )
        sys.stdout.write("=" * 40 + "\n")
        return

    import json as json_lib

    import kit.api as api

    brain = api.get_brain()
    stats = brain.get_stats()

    if getattr(args, "json", False):
        sys.stdout.write(json_lib.dumps(stats, indent=2) + "\n")
    else:
        gqi = stats.get("gqi", {})
        sys.stdout.write("TITANIUM KERNEL PULSE (STAGE 5.1)\n")
        sys.stdout.write("=" * 40 + "\n")
        sys.stdout.write(f"Quality Score: {gqi.get('quality_score', 0):.2f} / 1.00\n")
        sys.stdout.write(f"Entropy Score: {gqi.get('entropy_score', 0):.4f}\n")
        sys.stdout.write("-" * 40 + "\n")

        sys.stdout.write("PERFORMANCE:\n")
        sys.stdout.write(f"  Recall Hit Rate: {gqi.get('recall_hit_rate', 0):.1f}%\n")
        sys.stdout.write(f"  Avg Latency:     {gqi.get('avg_recall_latency_ms', 0):.2f}ms\n")

        sys.stdout.write("\nHYGIENE:\n")
        sys.stdout.write(f"  Symbol Debt:     {gqi.get('symbol_debt_ratio', 0):.1f}%\n")
        sys.stdout.write(f"  Symbol Health:   {gqi.get('symbol_health', 0):.1f}% (Hierarchical)\n")
        sys.stdout.write(f"  Duplicates:      {gqi.get('duplicate_ratio', 0):.1f}%\n")
        sys.stdout.write(f"  Orphan Edges:    {gqi.get('orphan_ratio', 0):.1f}%\n")

        sys.stdout.write("\nCOMPACTION:\n")
        sys.stdout.write(f"  Canonicalized:   {gqi.get('canonical_count', 0)}\n")
        sys.stdout.write(f"  Merged Records:  {gqi.get('merged_count', 0)}\n")

        sys.stdout.write("\nNAMESPACES:\n")
        for ns, count in stats.get("namespaces", {}).items():
            sys.stdout.write(f"  - {ns:12} : {count}\n")

        # 1.2.5STAGE5.5: SRE Drift Metrics
        with brain.get_connection(readonly=True) as conn:
            drift_avg = conn.execute("SELECT AVG(final_score) FROM symbol_drift_events").fetchone()[0] or 0.0
            pending_proposals = conn.execute(
                "SELECT COUNT(*) FROM symbol_reconciliation_proposals WHERE status = 'pending'"
            ).fetchone()[0]

        sys.stdout.write("\nEVOLUTION (SRE 5.5):\n")
        sys.stdout.write(f"  Avg Drift Score: {drift_avg:.4f}\n")
        sys.stdout.write(f"  Pending Proposals: {pending_proposals}\n")

        sys.stdout.write("=" * 40 + "\n")


@kit_command(
    name="retention",
    namespace=CommandNamespace.CORE,
    description="Execute snapshot lifecycle (tiered retention policy)",
    side_effect=CommandSideEffect.MUTATION,
)
def handle_retention(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit retention' command (1.2.5STAGE5.1)."""
    import kit.api as api
    from kit.core.kit_retention import RetentionPolicy, execute_retention

    policy = RetentionPolicy(keep_hot=getattr(args, "hot", 3), dry_run=getattr(args, "dry_run", False))

    brain = api.get_brain()
    print_diagnostic(f"Retention: Running lifecycle purge (Dry-run: {policy.dry_run})...")
    report = execute_retention(brain, policy)

    print_diagnostic(
        f"Retention Complete: {report['purged']} purged, {report['preserved']} preserved, {report['errors']} errors."
    )
    print("OK")


@kit_command(name="metrics", namespace=CommandNamespace.DIAGNOSTIC, description="Alias for stats (Longevity Metrics)")
def handle_metrics(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Alias for 'kit stats'."""
    return handle_stats(args, print_diagnostic, **kwargs)


@kit_command(name="status", namespace=CommandNamespace.DIAGNOSTIC, description="Alias for stats --verbose")
def handle_status(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit status' command."""
    args.verbose = True
    return handle_stats(args, print_diagnostic, **kwargs)


@kit_command(
    name="preflight",
    namespace=CommandNamespace.MEMORY,
    description="Run cognitive governance checks before committing",
    side_effect=CommandSideEffect.READ_ONLY,
)
def handle_preflight(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit preflight' command."""
    import kit.api as api
    from kit.core.kit_governance import run_preflight
    from kit.core.kit_platform import FAST_TIMEOUT, read_stdin_fail_fast

    # Preflight expects diff via stdin
    diff_text = read_stdin_fail_fast(timeout=FAST_TIMEOUT)
    brain = api.get_brain()

    result = run_preflight(
        commit_msg=getattr(args, "message", ""),
        brain=brain,
        strict_mode=getattr(args, "strict", False),
        diff_text=diff_text,
    )

    if result.status == "block":
        print_diagnostic(f"[FAIL] PREFLIGHT BLOCK: Score {result.score:.2f}")
        for issue in result.issues:
            print_diagnostic(f"  - [{issue['type']}] {issue['message']}")
        sys.exit(1)
    elif result.status == "warn":
        print_diagnostic(f"[WARN] PREFLIGHT WARN: Score {result.score:.2f}")
        for issue in result.issues:
            print_diagnostic(f"  - [{issue['type']}] {issue['message']}")
    else:
        print_diagnostic(f"[OK] PREFLIGHT PASS: Score {result.score:.2f}")


@kit_command(
    name="compact",
    namespace=CommandNamespace.CORE,
    description="Consolidate semantically redundant memories into Canonical entries",
    side_effect=CommandSideEffect.MUTATION,
)
def handle_compact(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit compact' command (1.2.5STAGE5.3)."""
    import kit.api as api

    brain = api.get_brain()
    ns = getattr(args, "namespace", "shared")
    print_diagnostic(f"Compacting namespace '{ns}' into Canonical Model...")
    report = execute_compaction(brain, namespace=ns)
    print_diagnostic(
        f"Compaction Complete: {report['canonicalized']} canonicalized, {report['merged']} records merged."
    )
    print("OK")


@kit_command(
    name="repair",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="Plan bounded drift repair or run explicit symbol-debt repair",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={
        "plan": "bool (generate repair plan artifact)",
        "diff": "bool (render replayable diff candidates)",
        "apply": "bool (guarded apply entry point)",
        "confirm": "bool (required for apply)",
        "json": "bool (machine readable output)",
        "symbol_debt": "bool (legacy explicit symbol repair)",
    },
)
def handle_repair(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit repair' command (Repair Contract v1)."""
    import json as json_lib

    try:
        mode = validate_repair_mode(args)
    except ValueError as exc:
        print_diagnostic(f"Error: {exc}")
        sys.exit(1)

    if mode == "symbol_debt":
        import kit.api as api

        brain = api.get_brain()
        print_diagnostic("Repairing symbol debt...")
        repaired = repair_symbol_debt(brain)
        print_diagnostic(f"Repair Complete: {repaired} symbols assigned.")
        print("OK")
        return

    plan_document = build_repair_plan()
    is_valid, validation_error = validate_plan_payload(plan_document.model_dump(mode="json"))
    if not is_valid:
        print_diagnostic(f"FAILED: repair plan schema invalid: {validation_error}")
        sys.exit(1)

    if mode == "plan":
        if getattr(args, "json", False):
            sys.stdout.write(json_lib.dumps(plan_document.model_dump(mode="json"), indent=2) + "\n")
            return
        sys.stdout.write(render_repair_plan(plan_document))
        return

    if mode == "diff":
        diff_text = render_repair_diff(plan_document)
        if getattr(args, "json", False):
            sys.stdout.write(
                json_lib.dumps(
                    {
                        "plan": plan_document.model_dump(mode="json"),
                        "diff": diff_text,
                    },
                    indent=2,
                )
                + "\n"
            )
            return
        sys.stdout.write(diff_text)
        return

    apply_result = apply_repair_plan(plan_document, confirm=getattr(args, "confirm", False))
    if getattr(args, "json", False):
        sys.stdout.write(json_lib.dumps(apply_result, indent=2) + "\n")
    else:
        print_diagnostic(
            f"Repair apply blocked: {apply_result.get('reason')}. "
            "Review `kit repair --diff` and materialize changes manually."
        )
    sys.exit(1)


@kit_command(name="where", namespace=CommandNamespace.RUNTIME, description="Show current memory context and brain path")
def handle_where(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit where' command."""
    import kit.api as api

    brain = api.get_brain()
    sys.stdout.write(f"CWD:   {Path.cwd()}\n")
    sys.stdout.write(f"Local: {brain.db_path}\n")


@kit_command(
    name="doctor",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="System Self-Healing: Audit and repair common workspace/kernel issues",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={
        "mode": "safe | aggressive",
        "heal": "bool (execute repair sequence)",
        "migrate-memory": "bool (v1.2.3 -> v1.2.5)",
        "json": "bool (machine readable output)",
    },
)
def handle_doctor(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit doctor' command."""
    import json as json_lib

    import kit.api as api

    root_path = Path.cwd()
    brain = api.get_brain()

    report_data = {
        "version": get_cli_version(),
        "mode": "unknown",
        "sqlite": "unknown",
        "wal": "unknown",
        "router": "OK",
        "global_db": "unknown",
        "vantage": "unknown",
        "alignment": "unknown",
        "entropy": 0.0,
    }

    # v1.2.5: Version Alignment Layer (SVTL)
    import importlib.metadata

    try:
        pip_v = importlib.metadata.version("memory-share-kit")
    except importlib.metadata.PackageNotFoundError:
        pip_v = "development"

    report_data["pip_version"] = pip_v

    if not getattr(args, "json", False):
        print_diagnostic("Kit Doctor 1.2.5GLOBAL-RUNTIME (Heal & Align)")

    if getattr(args, "heal", False):
        if not getattr(args, "json", False):
            print_diagnostic("Starting system-wide healing sequence...")
        from kit.core.kit_hygiene import perform_hygiene_cleanup

        removed = perform_hygiene_cleanup(root_path, dry_run=False)
        for f in removed:
            if not getattr(args, "json", False):
                print_diagnostic(f"  [HEALED] Removed noise artifact: {f}")

        # 2. Cognitive Hygiene (Flow v0.1.2)
        if not getattr(args, "json", False):
            print_diagnostic("  [HEALED] Purging stale cognitive transactions...")
        with api.get_brain().get_connection() as conn:
            # Delete unbaked observations from failed/stale transactions
            cursor = conn.execute("""
                DELETE FROM observations 
                WHERE is_baked = 0 
                AND json_extract(metadata, '$._flow_id') IS NOT NULL
                AND json_extract(metadata, '$._flow_id') IN (SELECT id FROM flow_runs WHERE state = 'failed')
            """)
            obs_removed = cursor.rowcount

            tx_removed = cursor.rowcount

        # 3. Symbol Repair (1.2.5STAGE5.2)
        if not getattr(args, "json", False):
            print_diagnostic("  [HEALED] Repairing symbol debt...")
        repaired_symbols = repair_symbol_debt(api.get_brain())

        if not getattr(args, "json", False):
            print_diagnostic(
                f"Healing complete. {len(removed)} artifacts purged. {obs_removed} unbaked observations cleaned. {tx_removed} failed transactions archived. {repaired_symbols} symbols repaired."
            )
    else:
        # Default diagnostic scan
        from kit.core.kit_hygiene import generate_hygiene_report

        report = generate_hygiene_report(root_path)
        report_data["entropy"] = report.noise_score
        if report.noise_score > 0.1:
            if not getattr(args, "json", False):
                print_diagnostic(f"[WARN] High noise score detected ({report.noise_score:.2f}).")
                print_diagnostic("   Run 'kit doctor --heal' to purge noise.")
        else:
            if not getattr(args, "json", False):
                print_diagnostic("[OK] Workspace hygiene is within stable bounds.")

    # --- System Startup Check (v1.2.5 Production Hardening) ---
    from kit.core.kit_sealing import seal_kernel, verify_kernel_seal

    db_path = brain.db_path
    seal_info = verify_kernel_seal(db_path)
    if seal_info["status"] == "sealed":
        report_data["kernel_seal"] = f"v{seal_info['version']} (Strict)"
    else:
        report_data["kernel_seal"] = f"unsealed ({seal_info.get('reason', 'Missing')})"
        if getattr(args, "fix", False):
            seal_kernel(db_path)
            report_data["kernel_seal"] = "v1.2.5 (Restored)"

    if not getattr(args, "json", False):
        from kit.core.kit_env import ExecutionMode, get_execution_mode

        print_diagnostic("\n[SYSTEM HEALTH]")
        print_diagnostic(f"  Runtime Mode: {get_execution_mode().value}")
        print_diagnostic(f"  SQLite:       {report_data['sqlite']}")
        print_diagnostic(f"  WAL Mode:     {report_data['wal']}")
        print_diagnostic(f"  Router:       {report_data['router']}")
        print_diagnostic(f"  Kernel Seal:  {report_data['kernel_seal']}")
        print_diagnostic(f"  Global DB:    {report_data['global_db']}")

    # --- VIM: Version Identity Map (Production Grade) ---
    v_cli = get_cli_version()
    if not getattr(args, "json", False):
        print_diagnostic("\n[VERSION IDENTITY]")
        print_diagnostic(f"  Distribution: {v_cli}")

        # 1. Identity Analysis (AVS)
        if "-dev" in v_cli:
            print_diagnostic("  Identity:     ✅ DEVELOPMENT (LOCAL SOURCE)")
        else:
            print_diagnostic("  Identity:     ✅ DISTRIBUTION (STABLE RELEASE)")

        # 2. Execution vs Cognitive (Kernel Compatibility)
        from kit.core.kit_sealing import SEALED_VERSION

        kernel_v = seal_info.get("version", "unknown")
        print_diagnostic(f"  Cognitive:    {kernel_v}")

        # Semantic Compatibility check (v1.2.5 Epoch)
        if kernel_v.startswith(INTERNAL_EPOCH):
            print_diagnostic(f"  Compatibility: ✅ DETERMINISTIC ({INTERNAL_EPOCH}-epoch)")
            report_data["alignment"] = "OK"
        elif kernel_v == "unknown":
            print_diagnostic("  Compatibility:      ⚠️ UNKNOWN (UNSEALED)")
            report_data["alignment"] = "UNKNOWN"
        else:
            print_diagnostic("  Compatibility:      ❌ INCOMPATIBLE (SCHEMA DRIFT)")
            report_data["alignment"] = "INCOMPATIBLE"
    # --- Environment Audit ---
    if getattr(args, "migrate_memory", False):
        if not getattr(args, "json", False):
            print_diagnostic("\n[MEMORY MIGRATION]")

        from kit.core.memory_topology import MemoryTopologyFactory
        from kit.skills.migrate_brain import migrate_and_merge

        topo = brain.topology
        root = brain.root_path

        # Local Migration
        legacy_local = root / ".kit" / "brain.db"
        new_local = topo.resolve("local", "local")

        if legacy_local.exists():
            if not new_local.exists():
                if not getattr(args, "json", False):
                    print_diagnostic(f"  - Migrating: {legacy_local.name} -> {new_local.name}")
                try:
                    legacy_local.rename(new_local)
                    if not getattr(args, "json", False):
                        print_diagnostic("  ✔ Local memory migrated.")
                except Exception as e:
                    if not getattr(args, "json", False):
                        print_diagnostic(f"  ✖ Local migration failed: {e}")
            else:
                # Merge needed
                if not getattr(args, "json", False):
                    print_diagnostic(f"  - Merging: {legacy_local.name} into {new_local.name}")
                try:
                    # v1.2.5: Atomic Merge Strategy
                    temp_merged = new_local.with_suffix(".merged.db")
                    migrate_and_merge(str(legacy_local), str(new_local), str(temp_merged))

                    # Verify and swap
                    if temp_merged.exists():
                        # Backup current new_local just in case
                        backup = new_local.with_suffix(".premerge.bak")
                        new_local.rename(backup)
                        temp_merged.rename(new_local)

                        # Move legacy to bak
                        legacy_local.rename(legacy_local.with_suffix(".migrated.bak"))

                        if not getattr(args, "json", False):
                            print_diagnostic("  ✔ Local memory merged and schema aligned.")
                except Exception as e:
                    if not getattr(args, "json", False):
                        print_diagnostic(f"  ✖ Merge failed: {e}")

        # Global Migration
        global_kit_dir = topo.GLOBAL_KIT_HOME
        legacy_global = global_kit_dir / "global.db"
        new_global = topo.resolve("global", "global")

        if legacy_global.exists() and not new_global.exists():
            if not getattr(args, "json", False):
                print_diagnostic(f"  - Migrating Global: {legacy_global.name} -> {new_global.name}")
            try:
                legacy_global.rename(new_global)
                if not getattr(args, "json", False):
                    print_diagnostic("  ✔ Global memory migrated.")
            except Exception as e:
                if not getattr(args, "json", False):
                    print_diagnostic(f"  ✖ Global migration failed: {e}")

    try:
        from kit.core.kit_env import get_substrate_report

        substrate = get_substrate_report()

        mode = "production" if substrate["is_locked"] else "development"
        report_data["mode"] = mode
        if not getattr(args, "json", False):
            print_diagnostic(f"  Runtime Mode: {mode}")

        with api.get_brain().get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
            report_data["sqlite"] = "OK"
            if not getattr(args, "json", False):
                print_diagnostic("  SQLite:       OK")

            pragma_wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            report_data["wal"] = pragma_wal.upper()
            if not getattr(args, "json", False):
                print_diagnostic(f"  WAL Mode:     {pragma_wal.upper()}")

        if not getattr(args, "json", False):
            print_diagnostic("  Router:       OK")

        # Check Global DB
        from kit.api import resolve_paths

        _, global_db, _ = resolve_paths()
        if global_db.exists():
            report_data["global_db"] = "OK"
            if not getattr(args, "json", False):
                print_diagnostic("  Global DB:    OK")

        # v1.2.5: Explicit Vantage Sensor Check
        import shutil

        v_found = shutil.which("vantage") or shutil.which("kit-vantage")
        report_data["vantage"] = "OK" if v_found else "NOT FOUND"

        if not getattr(args, "json", False):
            print_diagnostic("\n[VANTAGE INTEGRITY]")
            if v_found:
                print_diagnostic("  Sensor:       OK")
            else:
                print_diagnostic("  Sensor:       ❌ NOT FOUND")
                print_diagnostic("  Action:       Install from https://github.com/so-sai/Vantage")
    except Exception as e:
        if not getattr(args, "json", False):
            print_diagnostic(f"[FAIL] HEALTH CHECK FAILED: {e}")
        report_data["error"] = str(e)

    # --- Vantage Integration (v1.2.5 Gating) ---
    if (getattr(args, "heal", False) or getattr(args, "json", False)) and not getattr(args, "no_vantage", False):
        import subprocess

        from kit.core.kit_vantage import VANTAGE_BIN

        if not getattr(args, "json", False):
            print_diagnostic("[VANTAGE INTEGRITY]")
        if VANTAGE_BIN and VANTAGE_BIN.exists():
            try:
                result = subprocess.run(
                    [str(VANTAGE_BIN), "verify-memory", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    try:
                        data = json_lib.loads(result.stdout) if result.stdout.strip() else {}
                        report_data["vantage"] = "OK"
                        report_data["vantage_data"] = data
                    except json_lib.JSONDecodeError:
                        report_data["vantage"] = "INVALID_JSON"
                        if not getattr(args, "json", False):
                            print_diagnostic("[WARN] Vantage output was not valid JSON")

                    if not getattr(args, "json", False):
                        records = data.get("records", 0)
                        valid = data.get("valid_hashes", 0)
                        print_diagnostic("[OK] Vantage: Memory integrity verified")
                        print_diagnostic(f"   Records: {records} | Valid: {valid}")
                else:
                    report_data["vantage"] = "FAIL"
                    if not getattr(args, "json", False):
                        print_diagnostic("[WARN] Vantage: Issues detected")
                        print_diagnostic("   Run `kit-vantage verify-memory -d` for details")
            except Exception as e:
                report_data["vantage"] = f"ERROR: {e}"
                if not getattr(args, "json", False):
                    print_diagnostic(f"[WARN] Vantage check failed: {e}")
        else:
            report_data["vantage"] = "NOT_INSTALLED"
            if not getattr(args, "json", False):
                print_diagnostic(
                    "[INFO] Vantage: Not installed (Run `cargo install --path .` from kit-vantage to enable)"
                )

    # --- Legacy/Core Doctor Dispatch (v1.2.5 Bridge) ---
    from kit.cli.doctor import run_doctor

    run_doctor(
        brain=brain,
        mode=getattr(args, "mode", "safe"),
        fix_shell=getattr(args, "fix_shell", False),
        migrate_memory=getattr(args, "migrate_memory", False),
        heal=getattr(args, "heal", False),
        skip_vantage=True,  # doctor is now diagnostic-only by default
    )

    if getattr(args, "json", False):
        sys.stdout.write(json_lib.dumps(report_data, indent=2) + "\n")


@kit_command(name="build", namespace=CommandNamespace.CORE, description="Fast structural build check (v1.2.5)")
def handle_build(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit build' - Fast structural check."""
    import os
    import py_compile
    from pathlib import Path

    print_diagnostic("Starting fast structural build check...")
    root = Path.cwd()
    py_files = list(root.glob("kit/**/*.py"))

    errors = 0
    for f in py_files:
        try:
            # v1.2.5: Syntax check only, no bytecode generation (os.devnull)
            py_compile.compile(str(f), doraise=True, cfile=os.devnull)
        except py_compile.PyCompileError as e:
            print_diagnostic(f"  [ERROR] {f}: {e}")
            errors += 1
        except Exception:
            # Handle Windows permission errors or other FS issues gracefully
            pass

    if errors == 0:
        print_diagnostic(f"[OK] Build check passed ({len(py_files)} files).")
        print("OK")
    else:
        print_diagnostic(f"[FAIL] Build check failed with {errors} errors.")
        sys.exit(1)


@kit_command(name="test", namespace=CommandNamespace.DIAGNOSTIC, description="Run TDD unit tests (pytest wrapper)")
def handle_test(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit test' - Unit test execution."""
    import subprocess

    print_diagnostic("Running TDD Unit Tests...")
    # Use sys.executable to ensure we use the same venv
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/"], capture_output=False)
    if res.returncode == 0:
        print("OK")
    else:
        sys.exit(res.returncode)




@kit_command(name="release", namespace=CommandNamespace.DIAGNOSTIC, description="Single Authority Release Gate (Verify + Tag + Push)")
def handle_release(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit release' - The ultimate release gate."""
    import subprocess
    from kit.cli.main import get_cli_version, handle_verify

    # 1. Epistemic Verification
    print_diagnostic(">>> Phase 1: Epistemic Verification...")
    try:
        handle_verify(args, print_diagnostic, **kwargs)
    except SystemExit as e:
        if e.code != 0:
            print_diagnostic("[FAIL] Release aborted: Verification failed.")
            sys.exit(1)

    # 2. Working Tree Hygiene
    print_diagnostic(">>> Phase 2: Structural Hygiene Check...")
    status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    if status.stdout.strip():
        print_diagnostic("[FAIL] Release aborted: Working tree is dirty. Commit your changes first.")
        print(status.stdout)
        sys.exit(1)

    # 3. Tagging & Anchoring
    version = get_cli_version()
    tag = f"v{version}"
    print_diagnostic(f">>> Phase 3: Anchoring reality at {tag}...")

    # Check if tag already exists
    tags = subprocess.run(["git", "tag", "-l", tag], capture_output=True, text=True)
    if tag in tags.stdout:
        print_diagnostic(f"[WARN] Tag {tag} already exists. Skipping tagging.")
    else:
        subprocess.run(["git", "tag", "-a", tag, "-m", f"release: {tag} titanium stable"], check=True)
        print_diagnostic(f"[OK] Tag {tag} created.")

    # 4. Global Synchronization
    print_diagnostic(">>> Phase 4: Global Synchronization (Pushing to main)...")
    try:
        # Push current branch
        subprocess.run(["git", "push", "origin", "main"], check=True)
        # Push specific tag to avoid conflicts with legacy tags
        subprocess.run(["git", "push", "origin", tag], check=True)
        print_diagnostic("[OK] Reality synchronized globally.")
    except subprocess.CalledProcessError as e:
        print_diagnostic(f"[FAIL] Global sync failed: {e}")
        sys.exit(1)

    print_diagnostic(f"\n[TITANIUM SEALED] {tag} is now Ground Truth.")


@kit_command(
    name="flow", namespace=CommandNamespace.CORE, description="Unified interactive loop (ask/run/learn/status)"
)
def handle_flow(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit flow' surface (v0.1.2)."""
    import kit.api as api
    from kit.flow.engine import FlowExecutor, FlowPlanner

    brain = api.get_brain()

    if getattr(args, "flow_command", None) == "run":
        yaml_path = Path(args.path)
        if not yaml_path.exists():
            print_diagnostic(f"Error: Flow file not found: {yaml_path}")
            sys.exit(1)

        print_diagnostic(f"Flow Runtime v0.1.2 - Executing: {yaml_path.name}")
        planner = FlowPlanner()
        spec = planner.load(yaml_path)

        executor = FlowExecutor(brain)
        success = executor.execute(spec)

        if success:
            print_diagnostic(f"[OK] Flow '{spec.name}' completed and committed successfully.")
        else:
            print_diagnostic(f"[FAIL] Flow '{spec.name}' failed. Check flow_transactions for details.")
            sys.exit(1)
    else:
        from kit.flow.surface import flow_decision_kernel

        print_diagnostic(f"Kit Flow Surface v1.2.5 (Brain: {brain.db_path.name})")
        # Default interactive behavior or help
        print_diagnostic("Usage: kit flow run <path.yaml>")


@kit_command(
    name="seal",
    namespace=CommandNamespace.CORE,
    description="Freeze memory kernel and generate structural seal",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"force": "bool (evict zombie handles)"},
)
def handle_seal(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit seal' command."""
    import subprocess

    import kit.api as api
    from kit.core import kit_lock
    from kit.core.kit_vantage import VANTAGE_BIN

    brain = api.get_brain()
    from kit.core.release_guard import ReleaseGuard

    ReleaseGuard.enforce_p0(brain)

    print_diagnostic(f"[SEAL] Sealing Cognitive Kernel: {brain.db_path.name}")

    try:
        # 1. Physical Database Seal
        kit_lock.seal(brain.db_path, brain.root_path, force_evict=getattr(args, "force", False))
        print_diagnostic("[OK] Memory state sealed logically (Forensic Guard active).")

        # 2. Structural Vantage Seal
        if VANTAGE_BIN and VANTAGE_BIN.exists():
            print_diagnostic("Establish structural baseline via Vantage...")
            subprocess.run([str(VANTAGE_BIN), "seal", "."], check=True)
            print_diagnostic("[OK] Structural seal established (VANTAGE.SEAL).")
        else:
            print_diagnostic("[WARN] Vantage not found. Skipping structural seal.")

        print("OK")
    except Exception:
        raise


@kit_command(
    name="introspect",
    namespace=CommandNamespace.META,
    description="Output the machine-readable command registry schema",
)
def handle_introspect(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit introspect'."""
    import json

    from kit.core.command_registry import registry

    schema = registry.to_dict()
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(schema, indent=2) + "\n")
    else:
        # human readable summary
        print("TITANIUM INTROSPECTION LAYER v1.2.5")
        for name, cmd in schema["commands"].items():
            print(f"  - {name:15} : {cmd['description']}")


@kit_command(
    name="trace",
    namespace=CommandNamespace.META,
    description="Show recent execution path telemetry",
    input_schema={
        "limit": "int (number of events)",
        "json": "bool (machine readable output)",
        "command_filter": "string (optional command filter)",
        "stage": "dispatch | parser | executor",
    },
)
def handle_trace(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit trace'."""
    import json as json_lib

    events = read_execution_events(
        limit=getattr(args, "limit", 20),
        command=getattr(args, "command_filter", None),
        stage=getattr(args, "stage", None),
    )
    if getattr(args, "json", False):
        sys.stdout.write(json_lib.dumps(events, indent=2) + "\n")
        return

    if not events:
        sys.stdout.write("No execution trace events found.\n")
        return

    sys.stdout.write("RECENT EXECUTION TRACE\n")
    sys.stdout.write("=" * 80 + "\n")
    for event in events:
        fallback = f" fallback={event['fallback_reason']}" if event.get("fallback_reason") else ""
        sys.stdout.write(
            f"{event['timestamp']} {event['stage']:8} {event['mode']:10} "
            f"{event['command']:12} {float(event['latency_ms']):8.3f}ms "
            f"{'OK' if event.get('success') else 'FAIL'}{fallback}\n"
        )
    sys.stdout.write("=" * 80 + "\n")


@kit_command(
    name="ingest",
    namespace=CommandNamespace.MEMORY,
    description="Consume structural events from Vantage stream (Bridge Layer)",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"watch": "bool (continuous monitoring)"},
)
def handle_ingest(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit ingest'."""
    import kit.api as api
    from kit.core.vantage_stream_consumer import VantageStreamConsumer

    brain = api.get_brain()
    from kit.core.release_guard import ReleaseGuard

    ReleaseGuard.enforce_p0(brain)

    consumer = VantageStreamConsumer(brain)

    if getattr(args, "watch", False):
        print_diagnostic("[BRIDGE] Monitoring Vantage stream... (Ctrl+C to stop)")
        try:
            consumer.watch()
        except KeyboardInterrupt:
            print_diagnostic("\n[BRIDGE] Stopped.")
    else:
        print_diagnostic("[BRIDGE] Processing Vantage stream batch...")
        processed = consumer.consume_batch()
        print_diagnostic(f"[OK] Processed {processed} events.")
        print("OK")


@kit_command(
    name="reconcile",
    namespace=CommandNamespace.MEMORY,
    description="Analyze symbol drift and list evolution proposals (Audit Mode)",
    input_schema={"verbose": "bool (show metrics)"},
)
def handle_reconcile(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit reconcile'."""
    import json

    import kit.api as api
    from kit.core.kit_sre import SREEngine

    brain = api.get_brain()

    print_diagnostic("SRE Reconciliation Report (Audit Mode)")
    print_diagnostic("-" * 40)

    with brain.get_connection(readonly=True) as conn:
        # 1. Show Drift Events
        drifts = conn.execute("""
            SELECT symbol, final_score, metrics_json, status 
            FROM symbol_drift_events 
            ORDER BY created_at DESC, final_score DESC 
            LIMIT 10
        """).fetchall()

        if drifts:
            print_diagnostic("\n[TOP DRIFTING SYMBOLS]")
            for symbol, score, metrics_json, status in drifts:
                print_diagnostic(f"  * {symbol:20} : Score {score:.4f} [{status}]")
                if getattr(args, "verbose", False):
                    metrics = json.loads(metrics_json)
                    print_diagnostic(f"    - Hard: {metrics.get('hard')}")
                    print_diagnostic(f"    - Soft: {metrics.get('soft')}")

        # 2. Show Pending Proposals
        proposals = conn.execute("""
            SELECT id, symbol, proposed_symbol, confidence, rationale 
            FROM symbol_reconciliation_proposals 
            WHERE status = 'pending'
        """).fetchall()

        if proposals:
            print_diagnostic("\n[EVOLUTION PROPOSALS]")
            for p_id, old, new, conf, rationale_json in proposals:
                rat = json.loads(rationale_json)
                print_diagnostic(f"  [{p_id}] {old} -> {new} (Conf: {conf:.2f})")
                print_diagnostic(f"       Rationale: {rat.get('evidence', 'N/A')}")
        else:
            print_diagnostic("\nNo pending evolution proposals.")


@kit_command(
    name="evolve",
    namespace=CommandNamespace.MEMORY,
    description="Authorize symbol evolution and update the Evolution Graph",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"proposal_id": "int (ID of proposal to approve)"},
)
def handle_evolve(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit evolve'."""
    import kit.api as api
    from kit.core.kit_sre import SREEngine

    proposal_id = getattr(args, "proposal_id", None)
    if proposal_id is None:
        print_diagnostic("Error: --proposal-id is required.")
        sys.exit(1)

    brain = api.get_brain()
    sre = SREEngine(brain)

    print_diagnostic(f"Executing Evolution for Proposal ID: {proposal_id}...")
    success = sre.evolve_symbol(proposal_id)

    if success:
        print_diagnostic("[OK] Evolution recorded. Symbol graph updated.")
        print("OK")
    else:
        print_diagnostic("[FAIL] Evolution failed. Proposal not found or internal error.")
        sys.exit(1)






@kit_command(
    name="unseal",
    namespace=CommandNamespace.CORE,
    description="Unlock memory kernel for modification",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"reason": "string (Audited reason for unlocking)"},
)
def handle_unseal(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit unseal' command."""
    import kit.api as api
    from kit.core import kit_lock

    reason = getattr(args, "reason", None)
    if not reason:
        print_diagnostic("Error: --reason is REQUIRED to unseal the kernel for auditing.")
        sys.exit(1)

    brain = api.get_brain()
    print_diagnostic(f"[UNSEAL] Unsealing Cognitive Kernel: {brain.db_path.name}")
    print_diagnostic(f"Reason: {reason}")
    try:
        kit_lock.unseal(brain.db_path, brain.root_path, reason=reason)
        print("OK")
    except Exception:
        raise


@kit_command(
    name="snapshot",
    namespace=CommandNamespace.CORE,
    description="Create a physical point-in-time snapshot with lineage tracking",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"reason": "string (lineage tracking message)"},
)
def handle_snapshot(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit snapshot' command (1.2.5STAGE5)."""
    import kit.api as api

    try:
        reason = getattr(args, "reason", "Manual snapshot via CLI")
        api.get_brain().snapshot(reason=reason)

        # v1.2.5: Vantage Integrity Gating
        import subprocess

        from kit.core.kit_vantage import VANTAGE_BIN

        if VANTAGE_BIN and VANTAGE_BIN.exists():
            subprocess.run([str(VANTAGE_BIN), "verify-memory"], capture_output=True)

        print("OK")
    except Exception:
        raise


@kit_command(
    name="restore",
    namespace=CommandNamespace.CORE,
    description="Restore memory kernel from a physical snapshot",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"path": "string (path to snapshot file)"},
)
def handle_restore(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit restore' command."""
    import kit.api as api

    path = Path(args.path) if getattr(args, "path", None) else None
    try:
        if api.restore(path):
            print("OK")
        else:
            raise RuntimeError("Restore failed.")
    except Exception:
        raise


@kit_command(
    name="run-skill",
    namespace=CommandNamespace.RUNTIME,
    description="Execute a cognitive skill or automation routine",
    side_effect=CommandSideEffect.MUTATION,
    input_schema={"skill": "string (name of skill)", "args": "list[string] (passthrough arguments)"},
)
def handle_run_skill(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit run-skill' command (ASR v1)."""
    import kit.api as api
    import kit.skills  # Ensure discovery
    from kit.skills.registry import SkillRegistry

    skill_name = getattr(args, "skill", None)
    passthrough_args = getattr(args, "args", [])

    if not skill_name:
        print_diagnostic("Usage: kit run-skill <skill_name> [json_args]")
        print_diagnostic("\nRegistered Skills:")
        skills = SkillRegistry.list_skills()
        if not skills:
            print_diagnostic("  (None)")
        for s in skills:
            print_diagnostic(f"  - {s['name']} (v{s['version']}) [Input: {s['input_model']}]")

        print_diagnostic("\nImplicit Legacy Skills:")
        print_diagnostic("  - snapshot: Atomic DB backup")
        sys.exit(1)

    try:
        # 1. Handle Legacy Skills
        if skill_name == "snapshot":
            _ = api.snapshot()
            print("OK")
            return

        # 2. Handle Registered ASR Skills
        skill_cls = SkillRegistry.get_skill(skill_name)
        if not skill_cls:
            raise ValueError(f"Unknown skill: {skill_name}")

        # Parse Input Data
        input_data = {}
        if passthrough_args:
            try:
                # Try parsing as JSON first
                import json

                input_data = json.loads(" ".join(passthrough_args))
            except json.JSONDecodeError:
                # Fallback to key=value pairs if simple
                for pair in passthrough_args:
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        input_data[k] = v
                    else:
                        raise ValueError(f"Invalid argument format: {pair}. Use JSON or key=value.") from None

        # Initialize and Run Skill
        skill_instance = skill_cls()
        # Skills usually run in a context of StateVectors, but for CLI we might pass empty/mock
        output = skill_instance.run(skill_cls.input_model(**input_data), context=[])

        if output.status == "SUCCESS":
            if not getattr(args, "json", False):
                print(json.dumps(output.results, indent=2))
                print("OK")
            else:
                import json as json_lib

                sys.stdout.write(json_lib.dumps(output.model_dump()) + "\n")
        else:
            print_diagnostic(f"Skill Failed: {output.results.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print_diagnostic(f"Execution Error: {e}")
        sys.exit(1)


@kit_command(
    name="verify-release",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="Tiered TDD Release Gate (P0/P1/P2)",
    side_effect=CommandSideEffect.READ_ONLY,
)
def handle_verify_release(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit verify-release' logic (v1.2.5)."""
    import subprocess

    import yaml

    gate_file = Path("kit-test-gate.yaml")
    if not gate_file.exists():
        sys.stderr.write("FAILED: kit-test-gate.yaml missing.\n")
        sys.exit(1)

    with open(gate_file, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print_diagnostic(f"Release Gate v1.2.5 - Strategy: {config.get('strategy')}")

    all_success = True
    for gate_id, gate in config.get("gates", {}).items():
        priority = gate.get("priority", 2)
        is_blocking = gate.get("blocking", True)
        tests = gate.get("tests", [])

        print_diagnostic(f"\n[GATE {gate_id}] (P{priority}) - {gate.get('description')}")

        gate_success = True
        for test_file in tests:
            print_diagnostic(f"  RUN: {test_file}...", level=logging.INFO)
            # v1.2.5: Use sys.executable to ensure we run in the same venv
            res = subprocess.run([sys.executable, "-m", "pytest", "-v", test_file], capture_output=True, text=True)

            if res.returncode == 0:
                print_diagnostic(f"  [PASS] {test_file}")
            else:
                print_diagnostic(f"  [FAIL] {test_file}")
                if getattr(args, "verbose", False):
                    print_diagnostic(res.stdout)
                gate_success = False

        if not gate_success:
            if is_blocking:
                print_diagnostic(f"[FAIL] BLOCK: Gate {gate_id} failed. Release aborted.")
                all_success = False
                break
            else:
                print_diagnostic(f"[WARN] Gate {gate_id} failed (Non-blocking).")
        else:
            print_diagnostic(f"[OK] PASS: Gate {gate_id}")

    if all_success:
        print("\nSUCCESS")
    else:
        sys.exit(1)


# --- CLI Entry Point ---


def main() -> None:
    """Main entry point for Titanium CLI."""
    # --- v1.2.5 Global Error Shield ---
    try:
        _main_impl()
    except PermissionError as e:
        if "sealed" in str(e).lower():
            sys.stderr.write("KIT-SEALED: run kit unseal --reason <msg>\n")
        else:
            sys.stderr.write(f"FAILED: {e}\n")
        sys.exit(1)
    except FileNotFoundError as e:
        if ".kit" in str(e).lower():
            sys.stderr.write("KIT-NOT-INIT: run kit init\n")
        else:
            sys.stderr.write(f"FAILED: {e}\n")
        sys.exit(1)
    except RuntimeError as e:
        sys.stderr.write(f"FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        import traceback

        traceback.print_exc()
        print_diagnostic(f"FAILED: {e}. Run 'kit doctor'")
        sys.exit(1)


def _main_impl() -> None:
    """Internal implementation of main CLI logic."""
    from kit.core.dispatcher import classify

    def _raw_repair_governance_mode() -> bool:
        return len(sys.argv) > 1 and sys.argv[1] == "repair" and "--symbol-debt" not in sys.argv[2:]

    # --- v1.2.5: Execution Dispatcher (zero-reasoning fast path) ---
    if len(sys.argv) > 1:
        dispatch_start = time.perf_counter()
        cmd = sys.argv[1]
        classified_mode = classify(cmd)
        raw_args = sys.argv[2:]
        has_option_flags = any(part.startswith("-") for part in raw_args)
        if classified_mode == "direct" and not has_option_flags:
            from kit.core.dispatcher import dispatch

            exit(dispatch(cmd, None))

        actual_mode = "standard" if classified_mode == "direct" and has_option_flags else classified_mode
        fallback_reason = None
        if classified_mode == "direct" and has_option_flags:
            fallback_reason = "option_flags_present"
        elif classified_mode == "standard":
            fallback_reason = "not_in_fast_path"
        elif classified_mode in {"routed", "diagnostic"}:
            fallback_reason = "semantic_handler_path"

        log_execution_event(
            command=cmd,
            mode=actual_mode,
            stage="dispatch",
            latency_ms=(time.perf_counter() - dispatch_start) * 1000,
            success=True,
            fallback_reason=fallback_reason,
            metadata={"classified_mode": classified_mode},
        )
    # --- ECL v2: Runtime Shield Enforcer (Removed in v1.2.5 Global Runtime Mode) ---
    kit_env.get_substrate_report()

    # --- Workspace Initialization Guard (v1.2.5) ---
    is_diagnostic = len(sys.argv) > 1 and sys.argv[1] in ["test", "build", "verify-release", "release"]
    
    if (
        len(sys.argv) > 1
        and sys.argv[1]
        not in ["init", "init-env", "--help", "-h", "--version", "-v", "where", "status", "stats", "trace"]
        and not is_diagnostic
        and not _raw_repair_governance_mode()
    ):
        sentinel = Path.cwd() / BOOTSTRAP_SENTINEL
        if not sentinel.exists():
            print(
                f"\nError: Workspace not initialized.\n"
                f"The sentinel file '{BOOTSTRAP_SENTINEL}' is missing.\n"
                f"\nRun:\n  kit init\n"
                f"\nThen retry your command.",
                file=sys.stderr,
            )
            sys.exit(1)
    
    if is_diagnostic:
        sentinel = Path.cwd() / BOOTSTRAP_SENTINEL
        if not sentinel.exists():
            print_diagnostic(f"[STATELESS] Running in ephemeral mode (sentinel '{BOOTSTRAP_SENTINEL}' missing).")


    _configure_console_encoding()
    if len(sys.argv) == 1:
        sys.argv.append("recall")

    parser_start = time.perf_counter()
    parser = argparse.ArgumentParser(
        description="SAMBrain CLI v1.2.5 - Global Runtime Edition", formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"kit {get_cli_version()}")
    parser.add_argument("--db", help="Path to project database")
    parser.add_argument("--isolated", action="store_true", help="Force isolation")
    subparsers = parser.add_subparsers(dest="command")

    p_introspect = subparsers.add_parser("introspect", help="Output the machine-readable command registry schema")
    p_introspect.add_argument("--json", action="store_true", help="Output in JSON format")

    # Command Definitions

    p_init = subparsers.add_parser("init", help="Initialize space")
    p_init.add_argument("--force", action="store_true")

    subparsers.add_parser("init-env", help="Standardize environment files")

    # v1.2.5: Reflection-based CLI (Clean Architecture)
    from kit.core.policy_schema import LEARN_TAGS

    try:
        with open(Path(__file__).resolve().parents[1] / "registry" / "kit_capabilities.json") as f:
            caps = json.load(f)["capabilities"]
    except Exception:
        caps = {}

    p_learn = subparsers.add_parser("learn", help=caps.get("learn", {}).get("help", "Ingest observation"))
    p_learn.add_argument("content", nargs="?", help="Content to learn (or use STDIN)")
    p_learn.add_argument("--uid")
    p_learn.add_argument("--tag", default="decision", choices=LEARN_TAGS, help="Cognitive tag (runtime schema-driven)")
    p_learn.add_argument("--kind", default="observation")
    p_learn.add_argument("--importance", type=float, default=0.5)
    p_learn.add_argument("--metadata", help="JSON metadata string")
    p_learn.add_argument("--namespace", default="shared", help="Memory namespace (e.g., auth, db, arch)")
    p_learn.add_argument("--symbol", help="Semantic symbol for the memory")

    p_recall = subparsers.add_parser("recall", help=caps.get("recall", {}).get("help", "Recall ranked context"))
    p_recall.add_argument("entities", nargs="*")
    p_recall.add_argument("--limit", type=int, default=10)
    p_recall.add_argument("--query", "-q", help="Explicit semantic search query (FTS)")
    p_recall.add_argument("--here", action="store_true")
    p_recall.add_argument("--with-global", action="store_true")
    p_recall.add_argument("--since", help="Filter by date (ISO)")
    p_recall.add_argument("--until", help="Filter by date (ISO)")

    subparsers.add_parser("context", help="Alias for recall --here")
    subparsers.add_parser("search", help="Hybrid search").add_argument("query")
    p_stats = subparsers.add_parser("stats", help="Kernel statistics")
    p_stats.add_argument("--json", action="store_true", help="Output in JSON format")
    p_stats.add_argument("--paths", action="store_true", help="Show execution path costs")
    p_stats.add_argument("--hotpaths", action="store_true", help="Show executor-heavy commands")
    p_stats.add_argument("--consistency", action="store_true", help="Show cross-layer drift checks")
    p_stats.add_argument("--limit", type=int, default=200, help="Telemetry sample size for --paths")

    subparsers.add_parser("metrics", help="Alias for stats (Longevity Metrics)")

    p_status = subparsers.add_parser("status", help="Detailed status")
    p_status.add_argument("--json", action="store_true", help="Output in JSON format")

    p_trace = subparsers.add_parser("trace", help="Show recent execution path telemetry")
    p_trace.add_argument("--limit", type=int, default=20, help="Number of events to show")
    p_trace.add_argument("--json", action="store_true", help="Output in JSON format")
    p_trace.add_argument("--command", dest="command_filter", help="Filter by command name")
    p_trace.add_argument("--stage", choices=["dispatch", "parser", "executor"], help="Filter by stage")

    subparsers.add_parser("where", help="Show environment")

    p_flow = subparsers.add_parser("flow", help="Workflow Runtime Control")
    f_sub = p_flow.add_subparsers(dest="flow_command")
    f_run = f_sub.add_parser("run", help="Run a flow YAML")
    f_run.add_argument("path", help="Path to flow.yaml")
    f_run.add_argument("--resume", action="store_true", help="Resume from checkpoint")

    p_preflight = subparsers.add_parser("preflight", help="Run commit checks")
    p_preflight.add_argument("--message", default="")
    p_preflight.add_argument("--strict", action="store_true")

    p_hygiene = subparsers.add_parser("hygiene", help="Audit workspace hygiene")
    p_hygiene.add_argument("--verbose", action="store_true")

    p_doctor = subparsers.add_parser("doctor", help="Repair system issues")
    p_doctor.add_argument("--mode", choices=["safe", "aggressive"], default="safe", help="Pruning mode")
    p_doctor.add_argument("--heal", action="store_true", help="Execute cleanup DAG and integrity repair")
    p_doctor.add_argument("--migrate-memory", action="store_true", help="Migrate legacy v1.2.3 memory paths to v1.2.5")
    p_doctor.add_argument("--fix-shell", action="store_true", help="Fix PowerShell/IDE environment drift")
    p_doctor.add_argument("--json", action="store_true", help="Output health report in JSON")
    p_doctor.add_argument("--no-vantage", action="store_true", help="Skip Vantage integrity check")

    p_verify_release = subparsers.add_parser("verify-release", help="Run Tiered TDD Release Gate")
    p_verify_release.add_argument("--verbose", action="store_true", help="Show full test output on failure")

    subparsers.add_parser("build", help="Fast structural build check")
    subparsers.add_parser("test", help="Run TDD unit tests")
    subparsers.add_parser("release", help="Single Authority Release Gate (Verify + Tag + Push)")

    p_repair = subparsers.add_parser("repair", help="Plan bounded drift repair")
    p_repair.add_argument("--plan", action="store_true", help="Generate repair plan artifact")
    p_repair.add_argument("--diff", action="store_true", help="Render replayable diff candidates")
    p_repair.add_argument("--apply", action="store_true", help="Guarded apply entry point")
    p_repair.add_argument("--confirm", action="store_true", help="Required confirmation for --apply")
    p_repair.add_argument("--json", action="store_true", help="Output in JSON format")
    p_repair.add_argument("--symbol-debt", action="store_true", help="Run legacy explicit symbol repair")

    p_compact = subparsers.add_parser("compact", help="Consolidate redundant memories")
    p_compact.add_argument("--namespace", default="shared", help="Namespace to compact")

    p_seal = subparsers.add_parser("seal", help="Freeze memory kernel")
    p_seal.add_argument("--force", action="store_true", help="Force evict zombie handles")

    p_unseal = subparsers.add_parser("unseal", help="Unlock memory kernel")
    p_unseal.add_argument("--reason", required=True, help="Reason for unsealing (Audited)")

    p_snapshot = subparsers.add_parser("snapshot", help="Create a kernel snapshot")
    p_snapshot.add_argument("--reason", help="Reason for snapshot (Lineage tracking)")

    p_retention = subparsers.add_parser("retention", help="Execute snapshot lifecycle")
    p_retention.add_argument("--hot", type=int, default=3, help="Strictly keep only the latest N snapshots")
    p_retention.add_argument("--dry-run", action="store_true", help="Don't delete files")
    p_restore = subparsers.add_parser("restore", help="Restore kernel from snapshot")
    p_restore.add_argument("--path", help="Path to snapshot (optional)")

    p_run_skill = subparsers.add_parser("run-skill", help="Execute a cognitive skill")
    p_run_skill.add_argument("skill", nargs="?", help="Name of the skill to execute")
    p_run_skill.add_argument("args", nargs="*", help="Passthrough arguments for the skill (JSON or key=value)")

    # 1.2.5STAGE5.5: SRE Commands
    p_reconcile = subparsers.add_parser("reconcile", help="Analyze symbol drift (Audit Mode)")
    p_reconcile.add_argument("--verbose", action="store_true")

    p_evolve = subparsers.add_parser("evolve", help="Authorize symbol evolution")
    p_evolve.add_argument("--proposal-id", type=int, required=True, help="ID of the proposal to approve")

    p_ingest = subparsers.add_parser("ingest", help="Consume structural stream (Bridge Layer)")
    p_ingest.add_argument("--watch", action="store_true", help="Monitor stream continuously")


    args = parser.parse_args()
    command_mode = classify(args.command) if args.command else "standard"
    telemetry_mode = "standard" if command_mode == "standard" else command_mode
    log_execution_event(
        command=args.command or "unknown",
        mode=telemetry_mode,
        stage="parser",
        latency_ms=(time.perf_counter() - parser_start) * 1000,
        success=True,
        metadata={"argv": sys.argv[1:]},
    )

    if args.command == "stats" and not (
        getattr(args, "paths", False) or getattr(args, "hotpaths", False) or getattr(args, "consistency", False)
    ):
        sentinel = Path.cwd() / BOOTSTRAP_SENTINEL
        if not sentinel.exists():
            print(
                f"\nError: Workspace not initialized.\n"
                f"The sentinel file '{BOOTSTRAP_SENTINEL}' is missing.\n"
                f"\nRun:\n  kit init\n"
                f"\nThen retry your command.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Initialize Kernel API
    should_init_kernel = not (
        args.command == "trace"
        or args.command in ["test", "build", "verify-release"]
        or (
            args.command == "stats"
            and (
                getattr(args, "paths", False) or getattr(args, "hotpaths", False) or getattr(args, "consistency", False)
            )
        )
        or (args.command == "repair" and not repair_requires_kernel(args))
    )

    if should_init_kernel:
        import kit.api as api

        api.init_kernel(db_path=Path(args.db) if args.db else None, mode="isolated" if args.isolated else "auto")

    # --- Execution Boundary Firewall (v1.2.5) ---
    from kit.core.kit_env import ExecutionMode, get_execution_mode

    current_mode = get_execution_mode()

    if current_mode == ExecutionMode.TEST:
        forbidden_mutations = {"doctor": args.command == "doctor" and args.heal, "init-env": args.command == "init-env"}
        for tool, active in forbidden_mutations.items():
            if active:
                print(f"\n[FIREWALL] Mutation blocked: '{tool}' is forbidden in TEST mode.", file=sys.stderr)
                sys.exit(1)

    # --- v1.2.5: Router Logging Isolation ---
    router_logger = logging.getLogger("kit.memory_router")
    router_logger.propagate = False

    # Dispatch via Registry
    try:
        cmd_tuple = registry.get_command(args.command)
        if cmd_tuple:
            _, handler = cmd_tuple
            executor_start = time.perf_counter()
            try:
                handler(args=args, print_diagnostic=print_diagnostic, current_context=Path.cwd().name)
                log_execution_event(
                    command=args.command,
                    mode=telemetry_mode,
                    stage="executor",
                    latency_ms=(time.perf_counter() - executor_start) * 1000,
                    success=True,
                )
            except Exception as exc:
                log_execution_event(
                    command=args.command,
                    mode=telemetry_mode,
                    stage="executor",
                    latency_ms=(time.perf_counter() - executor_start) * 1000,
                    success=False,
                    metadata={"error": str(exc)},
                )
                raise
        else:
            sys.stderr.write(f"Unknown command: {args.command}\n")
            sys.exit(1)
    finally:
        # v1.2.5: Ensure background workers are joined to release Windows file locks
        if should_init_kernel:
            import kit.api as api

            api.shutdown_kernel()


if __name__ == "__main__":
    main()
# titanium_verify
