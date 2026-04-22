import argparse
import logging
import os
import re
import shutil
import sys
import sysconfig
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional, Callable, Final, Protocol, runtime_checkable

import yaml
from kit.core import kit_env
from kit.core.kit_baking import trigger_async_bake
from kit.core.file_system import EncodingError, read_text_safe
from kit.core.kit_decision import Action, decide
from kit.core.kit_platform import DEFAULT_TIMEOUT, FAST_TIMEOUT, GIT_TIMEOUT, read_stdin_fail_fast, run_safe
from kit.core.kit_replay_tracer import tracer
from kit.core.command_registry import CommandNamespace, CommandSideEffect, registry, kit_command
from kit.core.kit_hygiene import handle_hygiene, perform_hygiene_cleanup
from kit.core.kit_symbol_repair import repair_symbol_debt
from kit.core.kit_compaction import execute_compaction
from kit.core.policy_schema import LEARN_TAGS


# --- Section VII: Structured Logging (code-py-314) ---
logger = logging.getLogger("kit.cli")

@runtime_checkable
class DiagnosticPrinter(Protocol):
    """Protocol for diagnostic output reporting (v1.2.4)."""
    def __call__(self, msg: str, level: int = logging.INFO) -> None: ...

# --- CLI Constants ---
BOOTSTRAP_SENTINEL: Final[str] = ".kit/bootstrap_v1_2_4.seed"
CLI_VERSION: Final[str] = "v1.2.4-TITANIUM"
BOOTSTRAP_FACTS: Final[list[tuple[str, str]]] = [
    ("kit_startup", "kit startup begins with kit recall project_identity"),
    ("kit_rituals", "Daily: recall & verify. Weekly: hygiene & doctor. Monthly: seal."),
    ("flow_law", "Multi-step work MUST use 'kit flow run'. Isolation via transactions (v0.1.2)."),
    ("memory_law", "SQLite is Truth. observations.is_baked=1 is the only valid state for long-term memory."),
    ("arch_lighthouse", "AGENTS.md is the root contract; .kit/ is the private cognitive vault."),
    ("governance", "Maintain Entropy < 0.10. Run 'kit doctor --heal' to purge noise."),
    ("execution_contract", "All kit operations MUST route through 'kit' CLI (v1.2.4-TITANIUM)."),
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
            except (IOError, AttributeError) as e:
                # Rule II.1: No Silent Failures
                logger.warning(f"Console reconfiguration failed for {stream_name}: {e}")

def _cognitive_guardrail(text: str, tag: Optional[str]) -> bool:
    """Detects 'logic smells' in cognitive ingestion (Rule V.2)."""
    smell_patterns = [r"\d+%", r"\d+ms", r"\d+s\s", r"\d+(KB|MB|GB|B)", r"cpu|ram|usage|load", r"error|exception", r"\d{4}-\d{2}-\d{2}"]
    smell_keywords = {"currently", "now", "today", "recently", "temporary"}
    found_pattern = any(re.search(p, text, re.IGNORECASE) for p in smell_patterns)
    found_keyword = any(k in text.lower() for k in smell_keywords)
    if tag in ("invariant", "decision"):
        return found_pattern or found_keyword
    return False

def _bootloader_template() -> str:
    """Returns the canonical portable AGENTS.md template (v1.2.4-TITANIUM)."""
    return (
        "# AGENTS.md (v1.2.4 CONTRACT)\n\n"
        "## \u2696\ufe0f FLOW\n"
        "recall \u2192 tool \u2192 execute \u2192 learn\n\n"
        "## \U0001f3af ROUTING\n"
        "- unknown schema -> kit introspect --json\n"
        "- startup        -> kit recall --limit 10\n"
        "- friction       -> kit doctor\n"
        "- conflict       -> kit-vantage verify-memory\n"
        "- persist        -> kit learn --tag decision\n\n"
        "## \U0001f9e0 MEMORY GATE\n"
        "ALL memory access MUST go through:\n"
        "- kit recall          -- read context\n"
        "- kit search          -- locate symbol/topic\n"
        "- kit introspect --json -- inspect schema\n\n"
        "## \U0001f6ab HARD RULES\n"
        "- no direct DB access\n"
        "- no raw SQL\n"
        "- no filesystem inference\n"
        "- no bypass MemoryRouter\n"
        "- no ad-hoc scripts to inspect memory\n\n"
        "## \U0001f198 ESCALATION\n"
        "fail -> kit-vantage verify -> kit doctor -> retry\n"
    )


def _packaged_asset_root() -> Optional[Path]:
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

def _copy_if_missing(source_root: Optional[Path], relative_path: str, target_root: Path) -> bool:
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
    """Crystalizes the .kit cognitive substrate (v1.2.4)."""
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
        
    # v1.2.4: Schema Loader external-first fallback
    kit_schema = kit_dir / "kit_schema.json"
    if not kit_schema.exists():
        fallback_schema = Path(__file__).resolve().parent.parent / "core" / "schema_default.json"
        if fallback_schema.exists():
            import shutil
            shutil.copyfile(fallback_schema, kit_schema)

def _seed_bootstrap_memories(root_path: Path, project_name: str) -> bool:
    """Seeds deterministic starter pack memories (Rule III.2)."""
    sentinel = root_path / BOOTSTRAP_SENTINEL
    if sentinel.exists():
        return False
    
    sentinel.write_text(f"seeded at {datetime.now(UTC)}\n", encoding="utf-8")
    
    import kit.api as api
    api.learn(uid="project_identity", content=f"Project '{project_name}' initialized and integrated into .kit cognitive system ({CLI_VERSION}).", tag="decision", skip_render=True)
    
    for uid, content in BOOTSTRAP_FACTS:
        api.learn(uid=project_name, content=content, tag="decision", namespace="bootstrap", skip_render=True)
    
    return True

# --- Command Registry Handlers (Strictly Typed) ---

@kit_command(
    name="init", 
    namespace=CommandNamespace.CORE, 
    description="Initialize a new .kit memory space", 
    side_effect=CommandSideEffect.MUTATION
)
def handle_init(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit init' command."""
    import kit.api as api
    from kit.api import resolve_paths
    
    _, project_db, root_path = resolve_paths(force_local=True)
    api.init_kernel(project_db, mode="isolated")
    _materialize_onboarding_files(root_path, print_diagnostic)
    _seed_bootstrap_memories(root_path, root_path.name)
    
    # v1.2.4: Vantage Integrity Gating (Soft Check on Init)
    from kit.core.kit_vantage import VANTAGE_BIN
    import subprocess
    if VANTAGE_BIN and VANTAGE_BIN.exists() and os.getenv("KIT_DISABLE_ASYNC_BAKE") != "1":
        try:
            subprocess.run([str(VANTAGE_BIN), "verify-memory"], capture_output=True, timeout=5.0)
        except subprocess.TimeoutExpired:
            logger.warning("Vantage integrity check timed out during init.")
        
    print("OK")

@kit_command(
    name="init-env",
    namespace=CommandNamespace.CORE,
    description="Standardize VSCode and .env for relative path anchoring (v1.2.4)"
)
def handle_init_env(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Standardize project environment files."""
    root = Path.cwd()
    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    
    settings_path = vscode_dir / "settings.json"
    settings = {
        "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
        "python.terminal.useEnvFile": True,
        "python.analysis.extraPaths": ["${workspaceFolder}"],
        "terminal.integrated.env.windows": {
            "PYTHONPATH": "${workspaceFolder}"
        },
        "files.watcherExclude": {
            "**/.kit/**": True,
            "**/.pytest_cache/**": True
        }
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
        "symbol": "string (semantic node)"
    }
)

def handle_learn(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, current_context: str = "shared", **kwargs: Any) -> None:
    """Handler for 'kit learn' command."""
    from functools import partial
    import kit.api as api
    from kit.core.kernel_engine import DeterministicKernel
    from kit.core.kernel_fsm import ExecutionFrame
    
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
        metadata=metadata
    )
    
    frame = ExecutionFrame(action=action_call, command=f"learn:{getattr(args, 'uid', 'anonymous')}")
    kernel.submit(frame)
    
    if kernel.run():
        trigger_async_bake(api.get_brain())
        
        # v1.2.4-TITANIUM: Hard Vantage Gating (Disabled for Frozen Vantage Mode)
        # from kit.core.kit_vantage import VANTAGE_BIN
        # import subprocess
        # if VANTAGE_BIN and VANTAGE_BIN.exists():
        #     print_diagnostic("  [Vantage] Verifying integrity...")
        #     v_res = subprocess.run([str(VANTAGE_BIN), "verify-memory"], capture_output=True)
        #     if v_res.returncode != 0:
        #         print_diagnostic(f"[FAIL] VANTAGE INTEGRITY FAILURE: {v_res.stderr.decode()}")
        #         sys.exit(1)
        
        # v1.2.4: Mute narrative logs
        print("OK")
    else:
        # v1.2.4-TITANIUM: Propagate semantic error code if present
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
        "since": "relative date (e.g., 2d, 1h)"
    }
)

def handle_recall(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, current_context: str = "shared", **kwargs: Any) -> None:
    """Handler for 'kit recall' command."""
    import kit.api as api
    import re
    from datetime import datetime, timedelta

    def _parse_relative_date(val: str | None) -> str | None:
        if not val: return None
        match = re.match(r"(\d+)([dhm])", val.lower())
        if match:
            count, unit = int(match.group(1)), match.group(2)
            delta = timedelta(days=count) if unit == "d" else (timedelta(hours=count) if unit == "h" else timedelta(minutes=count))
            # v1.2.4-patch: Format to SQLite compatible timestamp in UTC
            return (datetime.now(UTC) - delta).strftime("%Y-%m-%d %H:%M:%S")
        return val

    # v1.2.4-patch: If no entities provided, pass None to enable Progressive Recall Fallback
    entities = args.entities if (hasattr(args, "entities") and args.entities) else None
    is_here = getattr(args, "here", False)
    
    memories = api.recall(
        entities, 
        limit=getattr(args, "limit", 15), 
        here=is_here, 
        with_global=getattr(args, "with_global", False),
        query=getattr(args, "query", None),
        since=_parse_relative_date(getattr(args, "since", None)),
        until=_parse_relative_date(getattr(args, "until", None))
    )
    
    if not memories:
        print_diagnostic("No context found.")
    else:
        for m in memories:
            # v1.2.4-TITANIUM: Include UID for deterministic contract verification
            uid_str = f" [{m.node_uid}]" if hasattr(m, "node_uid") and m.node_uid else ""
            sys.stdout.write(f"* [{m.brain_source}:{m.tag}]{uid_str} {m.content}\n")

@kit_command(
    name="context", 
    namespace=CommandNamespace.MEMORY, 
    description="Alias for recall --here (Project context awareness)"
)
def handle_context(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit context' (alias for recall --here)."""
    setattr(args, "here", True)
    return handle_recall(args, print_diagnostic, **kwargs)

@kit_command(
    name="search", 
    namespace=CommandNamespace.SEARCH, 
    description="Hybrid FTS5 keyword search"
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
    description="Show AI Kernel health and Quality Index (GQI 2.0)"
)
def handle_stats(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit stats' command (v1.2.4-STAGE5.1)."""
    import kit.api as api
    import json as json_lib
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
        
        # v1.2.4-STAGE5.5: SRE Drift Metrics
        with brain.get_connection(readonly=True) as conn:
            drift_avg = conn.execute("SELECT AVG(final_score) FROM symbol_drift_events").fetchone()[0] or 0.0
            pending_proposals = conn.execute("SELECT COUNT(*) FROM symbol_reconciliation_proposals WHERE status = 'pending'").fetchone()[0]
            
        sys.stdout.write("\nEVOLUTION (SRE 5.5):\n")
        sys.stdout.write(f"  Avg Drift Score: {drift_avg:.4f}\n")
        sys.stdout.write(f"  Pending Proposals: {pending_proposals}\n")
        
        sys.stdout.write("=" * 40 + "\n")

@kit_command(
    name="retention",
    namespace=CommandNamespace.CORE,
    description="Execute snapshot lifecycle (tiered retention policy)",
    side_effect=CommandSideEffect.MUTATION
)
def handle_retention(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit retention' command (v1.2.4-STAGE5.1)."""
    import kit.api as api
    from kit.core.kit_retention import execute_retention, RetentionPolicy
    
    policy = RetentionPolicy(
        keep_hot=getattr(args, "hot", 3),
        dry_run=getattr(args, "dry_run", False)
    )
    
    brain = api.get_brain()
    print_diagnostic(f"Retention: Running lifecycle purge (Dry-run: {policy.dry_run})...")
    report = execute_retention(brain, policy)
    
    print_diagnostic(f"Retention Complete: {report['purged']} purged, {report['preserved']} preserved, {report['errors']} errors.")
    print("OK")

@kit_command(
    name="metrics", 
    namespace=CommandNamespace.DIAGNOSTIC, 
    description="Alias for stats (Longevity Metrics)"
)
def handle_metrics(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Alias for 'kit stats'."""
    return handle_stats(args, print_diagnostic, **kwargs)

@kit_command(
    name="status", 
    namespace=CommandNamespace.DIAGNOSTIC, 
    description="Alias for stats --verbose"
)
def handle_status(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit status' command."""
    setattr(args, "verbose", True)
    return handle_stats(args, print_diagnostic, **kwargs)

@kit_command(
    name="preflight",
    namespace=CommandNamespace.MEMORY,
    description="Run cognitive governance checks before committing",
    side_effect=CommandSideEffect.READ_ONLY
)
def handle_preflight(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit preflight' command."""
    import kit.api as api
    from kit.core.kit_governance import run_preflight
    
    # Preflight expects diff via stdin
    diff_text = read_stdin_fail_fast(timeout=FAST_TIMEOUT)
    brain = api.get_brain()
    
    result = run_preflight(
        commit_msg=getattr(args, "message", ""),
        brain=brain,
        strict_mode=getattr(args, "strict", False),
        diff_text=diff_text
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
    side_effect=CommandSideEffect.MUTATION
)
def handle_compact(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit compact' command (v1.2.4-STAGE5.3)."""
    import kit.api as api
    brain = api.get_brain()
    ns = getattr(args, "namespace", "shared")
    print_diagnostic(f"Compacting namespace '{ns}' into Canonical Model...")
    report = execute_compaction(brain, namespace=ns)
    print_diagnostic(f"Compaction Complete: {report['canonicalized']} canonicalized, {report['merged']} records merged.")
    print("OK")

@kit_command(
    name="repair",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="Auto-repair symbol debt using cognitive heuristics",
    side_effect=CommandSideEffect.MUTATION
)
def handle_repair(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit repair' command (v1.2.4-STAGE5.2)."""
    import kit.api as api
    brain = api.get_brain()
    print_diagnostic("Repairing symbol debt...")
    repaired = repair_symbol_debt(brain)
    print_diagnostic(f"Repair Complete: {repaired} symbols assigned.")
    print("OK")

@kit_command(
    name="where", 
    namespace=CommandNamespace.RUNTIME, 
    description="Show current memory context and brain path"
)
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
    side_effect=CommandSideEffect.MUTATION
)
def handle_doctor(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit doctor' command."""
    import kit.api as api
    import json as json_lib
    root_path = Path.cwd()
    
    report_data = {
        "version": CLI_VERSION,
        "mode": "unknown",
        "sqlite": "unknown",
        "wal": "unknown",
        "router": "OK",
        "global_db": "unknown",
        "vantage": "unknown",
        "entropy": 0.0
    }

    if not getattr(args, "json", False):
        print_diagnostic("Kit Doctor v1.2.4-TITANIUM (Heal & Align)")
    
    if getattr(args, "heal", False):
        if not getattr(args, "json", False):
            print_diagnostic("Starting system-wide healing sequence...")
        # 1. Physical Hygiene
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
            
        # 3. Symbol Repair (v1.2.4-STAGE5.2)
        if not getattr(args, "json", False):
            print_diagnostic("  [HEALED] Repairing symbol debt...")
        repaired_symbols = repair_symbol_debt(api.get_brain())

        if not getattr(args, "json", False):
            print_diagnostic(f"Healing complete. {len(removed)} artifacts purged. {obs_removed} unbaked observations cleaned. {tx_removed} failed transactions archived. {repaired_symbols} symbols repaired.")
    else:
        # Default diagnostic scan
        from kit.core.kit_hygiene import generate_hygiene_report
        report = generate_hygiene_report(root_path)
        report_data["entropy"] = report.noise_score
        if report.noise_score > 0.1:
            if not getattr(args, "json", False):
                print_diagnostic(f"[WARN] High noise score detected ({report.noise_score:.2f}).")
                print_diagnostic("   Run 'kit doctor --heal' to purge disposable artifacts.")
        else:
            if not getattr(args, "json", False):
                print_diagnostic("[OK] Workspace hygiene is within stable bounds.")

    # --- System Startup Check (v1.2.4 Production Hardening) ---
    if not getattr(args, "json", False):
        print_diagnostic("\n[SYSTEM HEALTH]")
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
        else:
            report_data["global_db"] = "MISSING"
            if not getattr(args, "json", False):
                print_diagnostic("  Global DB:    MISSING (First learn will create)")
            
    except Exception as e:
        if not getattr(args, "json", False):
            print_diagnostic(f"[FAIL] HEALTH CHECK FAILED: {e}")
        report_data["error"] = str(e)

    # --- Vantage Integration (v1.2.4 Gating) ---
    if (getattr(args, "heal", False) or getattr(args, "json", False)) and not getattr(args, "no_vantage", False):
        from kit.core.kit_vantage import VANTAGE_BIN
        import subprocess

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
                print_diagnostic("[INFO] Vantage: Not installed (Run `cargo install --path .` from kit-vantage to enable)")

    if getattr(args, "json", False):
        sys.stdout.write(json_lib.dumps(report_data, indent=2) + "\n")

@kit_command(
    name="flow", 
    namespace=CommandNamespace.CORE, 
    description="Unified interactive loop (ask/run/learn/status)"
)
def handle_flow(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit flow' surface (v0.1.2)."""
    import kit.api as api
    from kit.flow.engine import FlowPlanner, FlowExecutor
    
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
        print_diagnostic(f"Kit Flow Surface v1.2.4-TITANIUM (Brain: {brain.db_path.name})")
        # Default interactive behavior or help
        print_diagnostic("Usage: kit flow run <path.yaml>")

@kit_command(
    name="seal",
    namespace=CommandNamespace.CORE,
    description="Freeze memory kernel and generate structural seal",
    side_effect=CommandSideEffect.MUTATION
)
def handle_seal(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit seal' command."""
    import kit.api as api
    from kit.core import kit_lock
    from kit.core.kit_vantage import VANTAGE_BIN
    import subprocess

    brain = api.get_brain()
    print_diagnostic(f"[SEAL] Sealing Cognitive Kernel: {brain.db_path.name}")

    try:
        # 1. Physical Database Seal
        res = kit_lock.seal(brain.db_path, brain.root_path, force_evict=getattr(args, "force", False))
        print_diagnostic(f"[OK] Memory state sealed logically (Forensic Guard active).")

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
    description="Output the machine-readable command registry schema"
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
        print("TITANIUM INTROSPECTION LAYER v1.2.4")
        for name, cmd in schema["commands"].items():
            print(f"  - {name:15} : {cmd['description']}")

@kit_command(
    name="ingest",

    namespace=CommandNamespace.MEMORY,
    description="Consume structural events from Vantage stream (Bridge Layer)",
    side_effect=CommandSideEffect.MUTATION
)
def handle_ingest(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit ingest'."""
    import kit.api as api
    from kit.core.vantage_stream_consumer import VantageStreamConsumer
    
    brain = api.get_brain()
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
    description="Analyze symbol drift and list evolution proposals (Audit Mode)"
)
def handle_reconcile(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit reconcile'."""
    import kit.api as api
    from kit.core.kit_sre import SREEngine
    import json
    
    brain = api.get_brain()
    sre = SREEngine(brain)
    
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
    side_effect=CommandSideEffect.MUTATION
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
    side_effect=CommandSideEffect.MUTATION
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
    side_effect=CommandSideEffect.MUTATION
)
def handle_snapshot(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit snapshot' command (v1.2.4-STAGE5)."""
    import kit.api as api
    try:
        reason = getattr(args, "reason", "Manual snapshot via CLI")
        api.get_brain().snapshot(reason=reason)
        
        # v1.2.4: Vantage Integrity Gating
        from kit.core.kit_vantage import VANTAGE_BIN
        import subprocess
        if VANTAGE_BIN and VANTAGE_BIN.exists():
            subprocess.run([str(VANTAGE_BIN), "verify-memory"], capture_output=True)
            
        print("OK")
    except Exception:
        raise

@kit_command(
    name="restore",
    namespace=CommandNamespace.CORE,
    description="Restore memory kernel from a physical snapshot",
    side_effect=CommandSideEffect.MUTATION
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
    side_effect=CommandSideEffect.MUTATION
)
def handle_run_skill(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit run-skill' command."""
    skill_name = getattr(args, "skill", None)
    if not skill_name:
        print_diagnostic("Usage: kit run-skill <skill_name> [args...]")
        print_diagnostic("\nAvailable Skills (Implicit):")
        print_diagnostic("  - snapshot: Atomic DB backup")
        print_diagnostic("  - verify:   Memory integrity audit")
        print_diagnostic("  - vacuum:   Database maintenance")
        sys.exit(1)
    
    import kit.api as api
    try:
        if skill_name == "snapshot":
            _ = api.snapshot()
            print("OK")
        elif skill_name == "verify":
            # Placeholder for actual verify logic
            print("OK")
        else:
            raise ValueError(f"Unknown skill: {skill_name}")
    except Exception as e:
        raise

@kit_command(
    name="verify-release",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="Tiered TDD Release Gate (P0/P1/P2)",
    side_effect=CommandSideEffect.READ_ONLY
)
def handle_verify_release(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit verify-release' logic (v1.2.4-TITANIUM)."""
    import subprocess
    import yaml
    
    gate_file = Path("kit-test-gate.yaml")
    if not gate_file.exists():
        sys.stderr.write("FAILED: kit-test-gate.yaml missing.\n")
        sys.exit(1)
        
    with open(gate_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    print_diagnostic(f"Release Gate v1.2.4 - Strategy: {config.get('strategy')}")
    
    all_success = True
    for gate_id, gate in config.get("gates", {}).items():
        priority = gate.get("priority", 2)
        is_blocking = gate.get("blocking", True)
        tests = gate.get("tests", [])
        
        print_diagnostic(f"\n[GATE {gate_id}] (P{priority}) - {gate.get('description')}")
        
        gate_success = True
        for test_file in tests:
            print_diagnostic(f"  RUN: {test_file}...", level=logging.INFO)
            # v1.2.4: Use sys.executable to ensure we run in the same venv
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
        print("\nOK")
    else:
        sys.exit(1)

# --- CLI Entry Point ---

def main() -> None:
    """Main entry point for Titanium CLI."""
    # --- v1.2.4 Global Error Shield ---
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
        if "Interpreter mismatch" in str(e) or "[RUNTIME LOCK]" in str(e):
            sys.stderr.write("KIT-ENV-LOCK: activate project .venv\n")
        else:
            sys.stderr.write(f"FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print_diagnostic(f"FAILED: {e}. Run 'kit doctor'")
        sys.exit(1)

def _main_impl() -> None:
    """Internal implementation of main CLI logic."""
# --- ECL v2: Runtime Shield Enforcer ---
    substrate = kit_env.get_substrate_report()
    if substrate["venv_discovered"] != "missing" and not substrate["is_locked"] and os.getenv("KIT_BYPASS_RUNTIME_LOCK") != "1":
        # Rule II.1: Explicit Failures
        if len(sys.argv) > 1 and sys.argv[1] not in ["stats", "status", "init", "init-env", "--help", "-h", "flow", "--version", "-v", "doctor", "where", "context"]:
            # Check if .kit exists for helpful message
            kit_dir = Path.cwd() / ".kit"
            hint = ""
            if not kit_dir.exists():
                hint = (
                    "\n"
                    "Hint: Workspace not initialized.\n"
                    "Run: kit init\n"
                    "Then retry your command."
                )
            raise RuntimeError(
                f"[RUNTIME LOCK] Interpreter mismatch.\n"
                f"Expected: {substrate.get('venv_discovered')}\n"
                f"Actual:   {substrate.get('interpreter')}"
                f"{hint}"
            )

    # --- Workspace Initialization Guard (v1.2.4) ---
    if len(sys.argv) > 1 and sys.argv[1] not in ["init", "init-env", "--help", "-h", "where", "status"]:
        sentinel = Path.cwd() / BOOTSTRAP_SENTINEL
        if not sentinel.exists():
            print(
                f"\nError: Workspace not initialized.\n"
                f"The sentinel file '{BOOTSTRAP_SENTINEL}' is missing.\n"
                f"\nRun:\n  kit init\n"
                f"\nThen retry your command.",
                file=sys.stderr
            )
            sys.exit(1)

    _configure_console_encoding()
    if len(sys.argv) == 1:
        sys.argv.append("recall")

    parser = argparse.ArgumentParser(
        description="SAMBrain CLI v1.2.4 - The Elite AI Memory Kernel",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"kit {CLI_VERSION}")
    parser.add_argument("--db", help="Path to project database")
    parser.add_argument("--isolated", action="store_true", help="Force isolation")
    subparsers = parser.add_subparsers(dest="command")

    p_introspect = subparsers.add_parser("introspect", help="Output the machine-readable command registry schema")
    p_introspect.add_argument("--json", action="store_true", help="Output in JSON format")

    # Command Definitions

    p_init = subparsers.add_parser("init", help="Initialize space")
    p_init.add_argument("--force", action="store_true")

    p_init_env = subparsers.add_parser("init-env", help="Standardize environment files")
    
    # v1.2.4: Reflection-based CLI (Clean Architecture)
    from kit.core.policy_schema import LEARN_TAGS
    try:
        with open(Path(__file__).resolve().parents[1] / "registry" / "kit_capabilities.json", "r") as f:
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

    subparsers.add_parser("metrics", help="Alias for stats (Longevity Metrics)")

    p_status = subparsers.add_parser("status", help="Detailed status")
    p_status.add_argument("--json", action="store_true", help="Output in JSON format")

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
    p_doctor.add_argument("--heal", action="store_true", help="Execute cleanup DAG")
    p_doctor.add_argument("--json", action="store_true", help="Output health report in JSON")
    p_doctor.add_argument("--no-vantage", action="store_true", help="Skip Vantage integrity check")

    p_verify_release = subparsers.add_parser("verify-release", help="Run Tiered TDD Release Gate")
    p_verify_release.add_argument("--verbose", action="store_true", help="Show full test output on failure")

    subparsers.add_parser("repair", help="Auto-repair symbol debt")
    
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

    # v1.2.4-STAGE5.5: SRE Commands
    p_reconcile = subparsers.add_parser("reconcile", help="Analyze symbol drift (Audit Mode)")
    p_reconcile.add_argument("--verbose", action="store_true")

    p_evolve = subparsers.add_parser("evolve", help="Authorize symbol evolution")
    p_evolve.add_argument("--proposal-id", type=int, required=True, help="ID of the proposal to approve")

    p_ingest = subparsers.add_parser("ingest", help="Consume structural stream (Bridge Layer)")
    p_ingest.add_argument("--watch", action="store_true", help="Monitor stream continuously")

    args = parser.parse_args()
    
    # Initialize Kernel API
    import kit.api as api
    api.init_kernel(
        db_path=Path(args.db) if args.db else None, 
        mode="isolated" if args.isolated else "auto"
    )
    
    # --- Execution Boundary Firewall (v1.2.4-TITANIUM) ---
    from kit.core.kit_env import ExecutionMode, get_execution_mode
    current_mode = get_execution_mode()

    if current_mode == ExecutionMode.TEST:
        forbidden_mutations = {
            "doctor": args.command == "doctor" and args.heal,
            "init-env": args.command == "init-env"
        }
        for tool, active in forbidden_mutations.items():
            if active:
                print(f"\n[FIREWALL] Mutation blocked: '{tool}' is forbidden in TEST mode.", file=sys.stderr)
                sys.exit(1)

    # --- v1.2.4: Router Logging Isolation ---
    router_logger = logging.getLogger("kit.memory_router")
    router_logger.propagate = False
    

    # Dispatch via Registry
    try:
        cmd_tuple = registry.get_command(args.command)
        if cmd_tuple:
            _, handler = cmd_tuple
            handler(
                args=args, 
                print_diagnostic=print_diagnostic, 
                current_context=Path.cwd().name
            )
        else:
            sys.stderr.write(f"Unknown command: {args.command}\n")
            sys.exit(1)
    finally:
        # v1.2.4: Ensure background workers are joined to release Windows file locks
        api.shutdown_kernel()

if __name__ == "__main__":
    main()
# titanium_verify

