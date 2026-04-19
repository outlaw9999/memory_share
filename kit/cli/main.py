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
    """Returns the canonical portable AGENTS.md template (v1.2.4)."""
    return (
        "# AGENTS.md (v1.2.4-TITANIUM)\n\n"
        "## ðŸ§  Kit System Contract\n\n"
        "Kit is a deterministic workflow runtime for AI agents.\n\n"
        "All operations MUST go through `kit` CLI.\n\n"
        "---\n\n"
        "## ðŸš€ Execution Model (Flow v0.1.2)\n\n"
        "All multi-step tasks MUST use Flow Engine.\n\n"
        "### Lifecycle\n"
        "- PLAN â†’ YAML DAG definition\n"
        "- EXECUTE â†’ step-level isolated execution\n"
        "- COMMIT â†’ final bake of results (`is_baked=1`)\n\n"
        "--- \n\n"
        "## ðŸ¤  Cross-Repo Rule\n\n"
        "1. Start with: `kit recall project_identity`\n"
        "2. Never bypass CLI â†’ no direct DB access\n"
        "3. All mutations MUST go through `kit learn` or Flow Engine\n"
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

def _seed_bootstrap_memories(root_path: Path, project_name: str) -> bool:
    """Seeds deterministic starter pack memories (Rule III.2)."""
    sentinel = root_path / BOOTSTRAP_SENTINEL
    if sentinel.exists():
        return False
    
    import kit.api as api
    api.learn(uid="project_identity", content=f"Project '{project_name}' initialized and integrated into .kit cognitive system ({CLI_VERSION}).", tag="decision", skip_render=True)
    
    for uid, content in BOOTSTRAP_FACTS:
        api.learn(uid=project_name, content=content, tag="decision", namespace="bootstrap", skip_render=True)
    
    sentinel.write_text(f"seeded at {datetime.now(UTC)}\n", encoding="utf-8")
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
    print_diagnostic(f".kit crystallized successfully in {root_path}")

@kit_command(
    name="learn", 
    namespace=CommandNamespace.MEMORY, 
    description="Ingest a new observation", 
    side_effect=CommandSideEffect.MUTATION
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
        print_diagnostic("âš ï¸ COGNITIVE FRICTION: Potential dynamic/volatile data detected.")
    
    action_call = partial(
        api.get_brain().learn, 
        uid=getattr(args, "uid", None) or current_context, 
        content=content, 
        tag=args.tag, 
        kind=args.kind, 
        importance=args.importance
    )
    
    frame = ExecutionFrame(action=action_call, command=f"learn:{getattr(args, 'uid', 'anonymous')}")
    kernel.submit(frame)
    
    if kernel.run():
        trigger_async_bake(api.get_brain())
        print_diagnostic(f"Learned: [{getattr(args, 'uid', current_context)}] successfully ingested via Kernel.")
    else:
        print_diagnostic("Error: Kernel execution failed during ingestion.")
        sys.exit(1)

@kit_command(
    name="recall", 
    namespace=CommandNamespace.MEMORY, 
    description="Recall ranked context (Project + Global)"
)
def handle_recall(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, current_context: str = "shared", **kwargs: Any) -> None:
    """Handler for 'kit recall' command."""
    import kit.api as api
    entities = getattr(args, "entities", None) or [current_context]
    is_here = getattr(args, "here", False)
    
    memories = api.recall(
        entities, 
        limit=getattr(args, "limit", 15), 
        here=is_here, 
        with_global=getattr(args, "with_global", False)
    )
    
    if not memories:
        print_diagnostic("No context found.")
    else:
        for m in memories:
            sys.stdout.write(f"* [{m.brain_source}:{m.tag}] {m.content}\n")

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
    description="Show AI Kernel statistics (Hybrid)"
)
def handle_stats(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit stats' command."""
    import kit.api as api
    brain = api.get_brain()
    stats = brain.get_stats()
    
    for k, v in stats.items():
        sys.stdout.write(f"{k}: {v}\n")

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
        print_diagnostic(f"âŒ PREFLIGHT BLOCK: Score {result.score:.2f}")
        for issue in result.issues:
            print_diagnostic(f"  - [{issue['type']}] {issue['message']}")
        sys.exit(1)
    elif result.status == "warn":
        print_diagnostic(f"âš ï¸ PREFLIGHT WARN: Score {result.score:.2f}")
        for issue in result.issues:
            print_diagnostic(f"  - [{issue['type']}] {issue['message']}")
    else:
        print_diagnostic(f"âœ… PREFLIGHT PASS: Score {result.score:.2f}")

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
    root_path = Path.cwd()
    
    print_diagnostic("Kit Doctor v1.2.4-TITANIUM (Heal & Align)")
    
    if getattr(args, "heal", False):
        print_diagnostic("Starting system-wide healing sequence...")
        # 1. Physical Hygiene
        removed = perform_hygiene_cleanup(root_path, dry_run=False)
        for f in removed:
            print_diagnostic(f"  [HEALED] Removed noise artifact: {f}")
            
        # 2. Cognitive Hygiene (Flow v0.1.2)
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
            
            # Clean up failed transactions older than 1 hour
            cursor = conn.execute("""
                DELETE FROM flow_transactions 
                WHERE state = 'failed' 
                AND finished_at < datetime('now', '-1 hour')
            """)
            tx_removed = cursor.rowcount
            
        print_diagnostic(f"Healing complete. {len(removed)} artifacts purged. {obs_removed} unbaked observations cleaned. {tx_removed} failed transactions archived.")
    else:
        # Default diagnostic scan
        from kit.core.kit_hygiene import generate_hygiene_report
        report = generate_hygiene_report(root_path)
        if report.noise_score > 0.1:
            print_diagnostic(f"âš ï¸  High noise score detected ({report.noise_score:.2f}).")
            print_diagnostic("   Run 'kit doctor --heal' to purge disposable artifacts.")
        else:
            print_diagnostic("âœ… Workspace hygiene is within stable bounds.")

    # --- Vantage Integration (v1.2.4) ---
    skip_vantage = getattr(args, "no_vantage", False)
    if skip_vantage:
        print_diagnostic("⏭️  Vantage check skipped (--no-vantage)")
    else:
        from kit.core.kit_vantage import VANTAGE_BIN
        import subprocess
        import json

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
                    data = json.loads(result.stdout) if result.stdout.strip() else {}
                    records = data.get("records", 0)
                    valid = data.get("valid_hashes", 0)
                    print_diagnostic("✅ Vantage: Memory integrity verified")
                    print_diagnostic(f"   Records: {records} | Valid: {valid}")
                else:
                    print_diagnostic("⚠️  Vantage: Issues detected")
                    print_diagnostic("   Run `kit-vantage verify-memory -d` for details")
            except Exception as e:
                print_diagnostic(f"⚠️  Vantage check failed: {e}")
        else:
            print_diagnostic("ℹ️  Vantage: Not installed (Run `cargo install --path .` from kit-vantage to enable)")

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
            print_diagnostic(f"âœ… Flow '{spec.name}' completed and committed successfully.")
        else:
            print_diagnostic(f"âŒ Flow '{spec.name}' failed. Check flow_transactions for details.")
            sys.exit(1)
    else:
        from kit.flow.surface import flow_decision_kernel
        print_diagnostic(f"Kit Flow Surface v1.2.4-TITANIUM (Brain: {brain.db_path.name})")
        # Default interactive behavior or help
        print_diagnostic("Usage: kit flow run <path.yaml>")

# --- CLI Entry Point ---

def main() -> None:
    """Main entry point for Titanium CLI."""
# --- ECL v2: Runtime Shield Enforcer ---
    substrate = kit_env.get_substrate_report()
    if not substrate["is_locked"] and os.getenv("KIT_BYPASS_RUNTIME_LOCK") != "1":
        # Rule II.1: Explicit Failures
        if len(sys.argv) > 1 and sys.argv[1] not in ["stats", "status", "init", "--help", "-h", "flow"]:
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

    _configure_console_encoding()
    if len(sys.argv) == 1:
        sys.argv.append("recall")

    parser = argparse.ArgumentParser(
        description="SAMBrain CLI v1.2.4 - The Elite AI Memory Kernel",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", help="Path to project database")
    parser.add_argument("--isolated", action="store_true", help="Force isolation")
    subparsers = parser.add_subparsers(dest="command")

    # Command Definitions
    p_init = subparsers.add_parser("init", help="Initialize space")
    p_init.add_argument("--force", action="store_true")
    
    p_learn = subparsers.add_parser("learn", help="Ingest observation")
    p_learn.add_argument("--content")
    p_learn.add_argument("--uid")
    p_learn.add_argument("--tag", default="decision")
    p_learn.add_argument("--kind", default="observation")
    p_learn.add_argument("--importance", type=float, default=1.0)
    
    p_recall = subparsers.add_parser("recall", help="Recall ranked context")
    p_recall.add_argument("entities", nargs="*")
    p_recall.add_argument("--limit", type=int, default=15)
    p_recall.add_argument("--here", action="store_true")
    p_recall.add_argument("--with-global", action="store_true")

    subparsers.add_parser("context", help="Alias for recall --here")
    subparsers.add_parser("search", help="Hybrid search").add_argument("query")
    subparsers.add_parser("stats", help="Kernel statistics")
    subparsers.add_parser("status", help="Detailed status")
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
    p_doctor.add_argument("--no-vantage", action="store_true", help="Skip Vantage integrity check")

    args = parser.parse_args()
    
    # Initialize Kernel API
    import kit.api as api
    api.init_kernel(
        db_path=Path(args.db) if args.db else None, 
        mode="isolated" if args.isolated else "auto"
    )
    
    def print_diagnostic(msg: str, level: int = logging.INFO) -> None:
        """Standard diagnostic output callback."""
        sys.stderr.write(f"{msg}\n")
        logger.log(level, msg)

    # Dispatch via Registry
    cmd_tuple = registry.get_command(args.command)
    if cmd_tuple:
        _, handler = cmd_tuple
        handler(
            args=args, 
            print_diagnostic=print_diagnostic, 
            current_context=Path.cwd().name
        )
    else:
        print_diagnostic(f"Unknown command: {args.command}", level=logging.ERROR)
        sys.exit(1)

if __name__ == "__main__":
    main()
# titanium_verify

