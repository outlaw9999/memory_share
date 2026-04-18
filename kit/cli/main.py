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
    ("kit_startup", "kit startup begins with kit recall"),
    ("kit_rituals", "Daily: recall & verify. Weekly: stats & doctor. Monthly: seal."),
    ("vantage_law", "Structural signals from Vantage (v1.2.4) are physical truth. No hallucinations."),
    ("memory_law", "Markdown is volatile. SQLite is Truth. Log friction via kitf.ps1."),
    ("arch_lighthouse", "AGENTS.md is the root lighthouse; .kit/ is the private cognitive vault."),
    ("arch_layers", "L1 (Fast Guard) -> L2 (Structural/Vantage) -> L3 (Cognitive/SQLite)."),
    ("token_law", "Minimize static docs. Use 'kit --help' for syntax and 'kit recall' for rituals."),
    (
        "execution_contract",
        "CANONICAL ENTRYPOINT INVARIANT: All kit operations MUST route through 'python -m kit' or the installed 'kit' CLI.",
    ),
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
    """Returns the canonical AGENTS.md template."""
    return (
        "# memory-share-kit (v1.2.4-TITANIUM)\n\n"
        "Deterministic memory and governance for developers and AI agents.\n\n"
        "### 🧭 Startup Sequence\n"
        "```bash\n"
        "kit recall\n"
        "```\n"
        "1. **Zero Docs Policy:** Use `kit --help` for syntax.\n"
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
    
    onboarding_files = ["scripts/kitf.ps1"]
    for rel_path in onboarding_files:
        _copy_if_missing(asset_root, rel_path, kit_dir)

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
        print_diagnostic("⚠️ COGNITIVE FRICTION: Potential dynamic/volatile data detected.")
    
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
    
    memories, _ = api.recall(
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
        print_diagnostic(f"❌ PREFLIGHT BLOCK: Score {result.score:.2f}")
        for issue in result.issues:
            print_diagnostic(f"  - [{issue['type']}] {issue['message']}")
        sys.exit(1)
    elif result.status == "warn":
        print_diagnostic(f"⚠️ PREFLIGHT WARN: Score {result.score:.2f}")
        for issue in result.issues:
            print_diagnostic(f"  - [{issue['type']}] {issue['message']}")
    else:
        print_diagnostic(f"✅ PREFLIGHT PASS: Score {result.score:.2f}")

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
        removed = perform_hygiene_cleanup(root_path, dry_run=False)
        for f in removed:
            print_diagnostic(f"  [HEALED] Removed noise artifact: {f}")
        print_diagnostic(f"Healing complete. {len(removed)} artifacts purged.")
    else:
        # Default diagnostic scan
        from kit.core.kit_hygiene import generate_hygiene_report
        report = generate_hygiene_report(root_path)
        if report.noise_score > 0.1:
            print_diagnostic(f"⚠️  High noise score detected ({report.noise_score:.2f}).")
            print_diagnostic("   Run 'kit doctor --heal' to purge disposable artifacts.")
        else:
            print_diagnostic("✅ Workspace hygiene is within stable bounds.")

@kit_command(
    name="flow", 
    namespace=CommandNamespace.CORE, 
    description="Unified interactive loop (ask/run/learn/status)"
)
def handle_flow(args: argparse.Namespace, print_diagnostic: DiagnosticPrinter, **kwargs: Any) -> None:
    """Handler for 'kit flow' surface."""
    import kit.api as api
    from kit.flow.surface import flow_decision_kernel
    brain = api.get_brain()
    print_diagnostic(f"Kit Flow Surface v1.2.4-TITANIUM (Brain: {brain.db_path.name})")
    # Interactive flow loop placeholder

# --- CLI Entry Point ---

def main() -> None:
    """Main entry point for Titanium CLI."""
    # --- ECL v2: Runtime Shield Enforcer ---
    substrate = kit_env.get_substrate_report()
    if not substrate["is_locked"] and os.getenv("KIT_BYPASS_RUNTIME_LOCK") != "1":
        # Rule II.1: Explicit Failures
        if len(sys.argv) > 1 and sys.argv[1] not in ["stats", "status", "init", "--help", "-h", "flow"]:
            raise RuntimeError(
                f"[RUNTIME LOCK] Interpreter mismatch.\n"
                f"Expected: {substrate.get('venv_discovered')}\n"
                f"Actual:   {substrate.get('interpreter')}"
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
    subparsers.add_parser("flow", help="Interactive flow")
    
    p_preflight = subparsers.add_parser("preflight", help="Run commit checks")
    p_preflight.add_argument("--message", default="")
    p_preflight.add_argument("--strict", action="store_true")

    p_hygiene = subparsers.add_parser("hygiene", help="Audit workspace hygiene")
    p_hygiene.add_argument("--verbose", action="store_true")

    p_doctor = subparsers.add_parser("doctor", help="Repair system issues")
    p_doctor.add_argument("--heal", action="store_true", help="Execute cleanup DAG")

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
#   t i t a n i u m _ v e r i f y  
 