import argparse
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kit.core.kit_platform import DEFAULT_TIMEOUT, FAST_TIMEOUT, read_stdin_fail_fast, run_safe


def _cognitive_guardrail(text: str, tag: str | None) -> bool:
    """
    Returns True if content is 'smelly' (contains dynamic/temporal data).
    """
    # 1. Patterns: %, ms, MB, timestamps, usage metrics
    smell_patterns = [
        r"\d+%",
        r"\d+ms",
        r"\d+s\s",
        r"\d+(KB|MB|GB|B)",
        r"cpu|ram|usage|load|latency|throughput",
        r"error|exception|stacktrace",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}:\d{2}:\d{2}",
    ]

    # 2. Keywords: Temporal/Transient
    smell_keywords = {"currently", "now", "today", "recently", "temporary", "current", "latest", "moment", "instant"}

    found_pattern = any(re.search(p, text, re.IGNORECASE) for p in smell_patterns)
    found_keyword = any(k in text.lower() for k in smell_keywords)

    # Only guard 'invariant' and 'decision' tags strictly
    if tag in ("invariant", "decision"):
        return found_pattern or found_keyword
    return False


def main() -> None:
    if len(sys.argv) == 1:
        sys.argv.append("recall")

    parser = argparse.ArgumentParser(
        description="SAMBrain CLI v1.2.3 - The Elite AI Memory Kernel (Immortal Stability)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", help="Path to the project database (overrides default)")
    parser.add_argument(
        "--isolated", action="store_true", help="Force isolation: create/use .kit in CWD, ignore parents"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _init_p = subparsers.add_parser("init", help="Initialize a new .kit memory space in the current directory")

    learn_p = subparsers.add_parser("learn", help="Ingest a new observation")
    learn_p.add_argument("--uid", help="Node UID (node identity)")
    learn_p.add_argument("--kind", default="observation", help="Node kind (e.g., concept, bug, arch)")
    learn_p.add_argument("--content", help="The observation to remember")
    learn_p.add_argument("--importance", type=float, default=1.0, help="Importance [0.1 - 1.0]")
    learn_p.add_argument("--supersede", type=int, help="ID of the observation to supersede")
    learn_p.add_argument(
        "--tag",
        choices=["invariant", "decision", "preference", "note", "legacy"],
        default="decision",
        help="Fact alignment tag",
    )
    learn_p.add_argument(
        "--layer",
        "-l",
        choices=["working", "episodic", "semantic", "procedural"],
        default="episodic",
        help="Cognitive layer",
    )
    learn_p.add_argument("--global", action="store_true", dest="to_global", help="Learn into Global Brain")
    learn_p.add_argument("--auto", action="store_true", help="Use v1.2.3 intelligent routing (recommended)")
    learn_p.add_argument("--namespace", default="shared", help="Namespace (e.g., project, agent:name)")
    learn_p.add_argument("--scope", help="Optional explicit scope (folder path)")
    learn_p.add_argument("--agent-id", help="Explicit Agent ID for attribution")
    learn_p.add_argument("--symbol", help="Anchor fact to a specific code symbol (AST node)")
    learn_p.add_argument("--hash", help="Structural hash of the symbol")
    learn_p.add_argument("--no-render", action="store_true", help="Skip manifest rendering (AGENTS.md) for batch speed")
    learn_p.add_argument("--file", help="Path to a JSON file containing a list of observations to learn")

    search_p = subparsers.add_parser("search", help="Hybrid FTS5 keyword search")
    search_p.add_argument("query", help="Keyword or phrase to search for")
    search_p.add_argument("--limit", type=int, default=15)
    search_p.add_argument("--at", help="Temporal snapshot (YYYY-MM-DD HH:MM:SS)")
    search_p.add_argument("--agent-id", help="Agent ID for recall boost")
    search_p.add_argument("--fast", action="store_true", help="Fast mode (skip heavy ranking)")

    recall_p = subparsers.add_parser("recall", help="Recall ranked context (Project + Global)")
    recall_p.add_argument("entities", nargs="*", help="Entity UIDs")
    recall_p.add_argument("--limit", type=int, default=15)
    recall_p.add_argument("--at", help="Temporal snapshot")
    recall_p.add_argument("--agent-id", help="Agent ID for recall boost")
    recall_p.add_argument("--here", action="store_true", help="Filter/Boost by current directory scope")
    recall_p.add_argument("--symbol", help="Recall context specifically for this code symbol")
    recall_p.add_argument("--query", help="Keyword search within recalled context")
    recall_p.add_argument("--with-global", action="store_true", help="Include Global Brain facts in recall")
    recall_p.add_argument("--fast", action="store_true", help="Fast mode (skip heavy ranking)")

    context_p = subparsers.add_parser("context", help="Alias for recall --here (Project context awareness)")
    context_p.add_argument("--limit", type=int, default=15)
    context_p.add_argument("--at", help="Temporal snapshot")
    context_p.add_argument("--agent-id", help="Agent ID for recall boost")
    context_p.add_argument("--symbol", help="Recall context specifically for this code symbol")
    context_p.add_argument("--query", help="Keyword search within context")
    context_p.add_argument("--with-global", action="store_true", help="Include Global Brain facts in recall")
    context_p.add_argument("--fast", action="store_true", help="Fast mode (skip heavy ranking)")

    reflect_p = subparsers.add_parser("reflect", help="Cognitive awareness: detect gaps and drift in diff")
    reflect_p.add_argument("file", nargs="?", help="File to reflect on (or use staged changes)")
    reflect_p.add_argument("--strict", action="store_true", help="Deprecated: use --mode strict")
    reflect_p.add_argument(
        "--mode", choices=["strict", "advisory", "silent"], default="advisory", help="Reflection strictness mode"
    )
    reflect_p.add_argument("--json", action="store_true", help="Structured JSON output")
    reflect_p.add_argument("--scope", help="Optional explicit scope (folder path)")
    reflect_p.add_argument("--here", action="store_true", help="Filter by current directory scope")

    blame_p = subparsers.add_parser("blame", help="Show architectural causality chain for a symbol")
    blame_p.add_argument("symbol", help="The code symbol (function, class, etc.)")

    subparsers.add_parser("where", help="Show current memory context and brain path")

    link_p = subparsers.add_parser("link", help="Create a semantic edge between two nodes")
    link_p.add_argument("--src", required=True)
    link_p.add_argument("--dst", required=True)
    link_p.add_argument("--rel", required=True, help="Relation type (e.g., DEPENDS_ON)")
    link_p.add_argument("--weight", type=float, default=1.0)

    subparsers.add_parser("stats", help="Show AI Kernel statistics (Hybrid)")

    bump_p = subparsers.add_parser("bump", help="Reinforce a memory (increment access count)")
    bump_p.add_argument("id", type=int, help="Observation ID")

    promote_p = subparsers.add_parser("promote", help="Promote episodic memories to semantic")
    promote_p.add_argument("--threshold", type=int, default=5, help="Access count threshold")

    doctor_p = subparsers.add_parser("doctor", help="System diagnostics and cognitive hygiene")
    doctor_p.add_argument("--mode", choices=["safe", "aggressive"], default="safe", help="Hygiene strictness level")
    doctor_p.add_argument("--check-agents", action="store_true", help="Run status check for AI agents")
    doctor_p.add_argument("--reset-cloud", action="store_true", help="Reset persisted cloud provider metrics")

    subparsers.add_parser("render", help="Force regenerate AI context files (.kit/context, AGENTS.md)")

    label_p = subparsers.add_parser("label", help="v1.2.4 feedback: Label an observation correctly")
    label_p.add_argument("--id", type=int, help="Observation ID to correct")
    label_p.add_argument("--correct", choices=["GLOBAL", "LOCAL"], required=True, help="Correct target brain")

    watch_p = subparsers.add_parser("watch", help="Stream cognitive events in real-time")
    watch_p.add_argument("--json", action="store_true", help="Output raw JSON stream")

    preflight_p = subparsers.add_parser("preflight", help="Run cognitive governance checks before committing")
    preflight_p.add_argument("-m", "--message", type=str, required=True, help="The commit message to evaluate")
    preflight_p.add_argument("--strict", action="store_true", help="Deprecated: use --mode strict")
    preflight_p.add_argument(
        "--mode", choices=["strict", "advisory", "silent"], default="strict", help="Preflight strictness mode"
    )
    preflight_p.add_argument("--json", action="store_true", help="Output raw JSON format")

    known_commands = [
        "init",
        "learn",
        "search",
        "recall",
        "context",
        "where",
        "link",
        "stats",
        "bump",
        "promote",
        "doctor",
        "render",
        "watch",
        "preflight",
        "blame",
        "reflect",
        "label",
    ]

    if len(sys.argv) > 1:
        potential_cmd = sys.argv[1]
        if not potential_cmd.startswith("-") and potential_cmd not in known_commands:
            plugin_name = f"kit-{potential_cmd}"
            plugin_path = shutil.which(plugin_name)

            if plugin_path:
                plugin_args = [plugin_path] + sys.argv[2:]
                try:
                    result = run_safe(plugin_args, timeout=DEFAULT_TIMEOUT)  # Standard 1s timeout
                    sys.exit(result.returncode)
                except Exception as e:
                    print(f"Error executing plugin '{plugin_name}': {e}", file=sys.stderr)
                    sys.exit(1)

    args = parser.parse_args()

    import kit.api as api

    db_path = Path(args.db).absolute() if args.db else None
    mode = "isolated" if args.isolated else "auto"
    api.init_kernel(db_path, mode=mode)

    def print_diagnostic(msg: object) -> None:
        print(msg, file=sys.stderr)

    is_tty = sys.stdout.isatty()
    current_context = Path.cwd().name

    try:
        if args.command == "init":
            from kit.api import resolve_paths

            # 1. Force local resolution and kernel re-initialization
            _, project_db, root_path = resolve_paths(force_local=True)
            api.init_kernel(project_db, mode="isolated")
            brain = api.get_brain()

            kit_dir = root_path / ".kit"

            # 2. Seed Project Identity Fact (Cognitive Onboarding)
            project_name = root_path.name
            init_date = datetime.now().strftime("%Y-%m-%d")
            api.learn(
                uid="project_identity",
                content=f"Project '{project_name}' initialized and integrated into .kit cognitive system on {init_date}.",
                tag="decision",
                importance=1.0,
                kind="arch",
            )

            # 3. Create manifest (AGENTS.md) if missing
            agents_md = root_path / "AGENTS.md"
            if not agents_md.exists():
                agents_md.write_text(
                    f"# Project Intelligence ({project_name})\n\n"
                    "This repository's architectural constraints and memory are managed by `.kit`.\n"
                    "AI Agents should treat this manifest as the canonical source of truth.\n\n"
                    "<!-- GENERATED BY KIT START -->\n"
                    "<!-- GENERATED BY KIT END -->\n",
                    encoding="utf-8",
                )
                print_diagnostic(f"Created {agents_md.name}")

            # 4. Update .gitignore
            gitignore = root_path / ".gitignore"
            if gitignore.exists() or root_path.joinpath(".git").exists():
                content = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
                if ".kit/brain.db-*" not in content:
                    with open(gitignore, "a", encoding="utf-8") as f:
                        f.write("\n# .kit Memory Store\n.kit/brain.db-*\n.kit/brain.db.bak\n")
                    print_diagnostic(f"Updated {gitignore.name} to ignore SQLite WAL/SHM files")

            # 5. Render context removed from automatic cycle [v1.2.3 HOTFIX]
            # Use 'kit render' manually if needed.

            print_diagnostic(f".kit initialized successfully in {kit_dir}")
            print_diagnostic("Project identity 'project_identity' breathed into memory.")
            print_diagnostic("Run `kit learn --tag invariant 'Rule 1'` to start building your cognitive memory.")

        elif args.command == "learn":
            import json as json_lib

            observations: list[dict[str, Any]] = []

            if args.file:
                file_path = Path(args.file)
                if not file_path.exists():
                    print_diagnostic(f"Error: File {args.file} not found.")
                    sys.exit(1)

                with open(file_path, encoding="utf-8") as f:
                    try:
                        data = json_lib.load(f)
                        if isinstance(data, list):
                            observations = data  # type: ignore[assignment]
                        else:
                            observations = [data]
                    except Exception as e:
                        print_diagnostic(f"Error parsing JSON file: {e}")
                        sys.exit(1)
            else:
                content = args.content
                if not content:
                    content = read_stdin_fail_fast(timeout=FAST_TIMEOUT)

                if not content:
                    print_diagnostic("Error: No content provided. (Use --content, --file, or pipe data via STDIN)")
                    sys.exit(1)

                observations = [
                    {
                        "content": content,
                        "tag": args.tag,
                        "uid": args.uid,
                        "kind": args.kind,
                        "importance": args.importance,
                        "layer": args.layer,
                        "to_global": args.to_global,
                        "supersede_id": args.supersede,
                        "namespace": args.namespace,
                        "scope": args.scope,
                        "agent_id": args.agent_id,
                        "symbol": args.symbol,
                        "hash": args.hash,
                    }
                ]

            total_obs = len(observations)
            success_count = 0
            if total_obs > 1:
                print_diagnostic(f"Starting batch ingestion of {total_obs} observations...")

            for i, obs in enumerate(observations, 1):
                try:
                    content = obs.get("content")
                    if not content:
                        continue

                    tag = obs.get("tag", args.tag)
                    uid = obs.get("uid", args.uid) or current_context
                    kind = obs.get("kind", args.kind)
                    importance = obs.get("importance", args.importance)
                    layer = obs.get("layer", args.layer)
                    to_global = obs.get("to_global", args.to_global)
                    supersede_id = obs.get("supersede_id", args.supersede)
                    namespace = obs.get("namespace", args.namespace)
                    scope = obs.get("scope", args.scope)
                    agent_id = obs.get("agent_id", args.agent_id)
                    symbol = obs.get("symbol", args.symbol)
                    struct_hash = obs.get("hash", args.hash)

                    # --- Cognitive Friction ---
                    if _cognitive_guardrail(content, tag):
                        # (Omitted diagnostic prints for brevity in batch mode if desired, but keeping them for now)
                        if not args.file:
                            print("\n" + "!" * 60, file=sys.stderr)
                            print("COGNITIVE FRICTION WARNING: DYNAMIC DATA DETECTED", file=sys.stderr)
                            # ... (rest of warning) ...

                    # --- v1.2.3 Auto-Routing ---
                    if getattr(args, "auto", False):
                        from kit.cli import auto_route

                        res = auto_route.route_content(content)
                        status = res["status"]

                        if status == "BLOCK":
                            print_diagnostic(f"[{i}/{total_obs}] FIREWALL: Secret detected. Entry BLOCKED.")
                            continue
                        if status == "DROP":
                            print_diagnostic(f"[{i}/{total_obs}] HYGIENE: Noise detected. Entry DROPPED.")
                            continue
                        if status == "SKIP":
                            print_diagnostic(f"[{i}/{total_obs}] IDEMPOTENCY: Duplicate detected. Entry SKIPPED.")
                            continue

                        struct_hash = res["hash"]
                        to_global = res["route"] == "GLOBAL"

                    fact_id = api.get_brain().learn(
                        uid=uid,
                        kind=kind,
                        content=content,
                        importance=importance,
                        layer=layer,
                        to_global=to_global,
                        supersede_id=supersede_id,
                        namespace=namespace,
                        scope=scope,
                        agent_id=agent_id,
                        symbol=symbol,
                        structural_hash=struct_hash,
                        tag=tag,
                        skip_render=args.no_render,
                    )
                    success_count += 1

                    if total_obs > 1:
                        if i % 100 == 0 or i == total_obs:
                            print_diagnostic(f"Progress: {i}/{total_obs} ingested...")
                    else:
                        target = "Global" if to_global else "Project"
                        print_diagnostic(f"Learned: [{uid}] -> {target} Brain (ID: {fact_id})")

                except Exception as e:
                    print_diagnostic(f"Error at index {i}: {e}")
                    continue

            if total_obs > 1:
                print_diagnostic(
                    f"\nCOMPLETED: {success_count}/{total_obs} observations successfully 'breathed' into memory."
                )

        elif args.command == "search":
            is_fast = getattr(args, "fast", False)
            memories = api.search(args.query, limit=args.limit, at=args.at, agent_id=args.agent_id, fast=is_fast)
            if is_tty:
                print_diagnostic(f"Hybrid search results for '{args.query}':\n")

            if not memories:
                print_diagnostic("No matches found.")
            else:
                for m in memories:
                    print(f"* [ID:{m.id}][{m.brain_source}:{m.node_uid}] {m.content} (score: {m.score:.2f})")

        elif args.command == "recall" or args.command == "context":
            entities: list[str] = args.entities if args.command == "recall" else []
            if args.command == "recall" and not entities:
                entities = [current_context]

            is_here = getattr(args, "here", False) or args.command == "context"
            is_fast = getattr(args, "fast", False)
            memories = api.recall(
                entities,
                limit=args.limit,
                at=args.at,
                agent_id=args.agent_id,
                here=is_here,
                symbol=args.symbol,
                query=args.query,
                with_global=args.with_global,
                fast=args.fast or (args.query is not None),
            )

            if is_tty:
                scope_str = f" [Scope: {api.get_brain().get_normalized_scope()}]" if is_here else ""
                print_diagnostic(f"Recalled context for {entities or 'current scope'}{scope_str}:\n")

            if not memories:
                print_diagnostic("No relevant memories found.")
            else:
                for m in memories:
                    source_tag = f"[{m.brain_source.upper()}]"
                    print(
                        f"* {source_tag}[ID:{m.id}][{m.node_uid}][{m.layer}:{m.namespace}][{m.created_at}][{m.importance:.1f}] {m.content}"
                    )

        elif args.command == "bump":
            if api.touch(args.id):
                print_diagnostic(f"Memory {args.id} reinforced.")
            else:
                print_diagnostic(f"Failed to reinforce memory {args.id}.")

        elif args.command == "promote":
            count = api.promote(args.threshold)
            print_diagnostic(f"Promoted {count} memories to Semantic layer (Threshold: {args.threshold}).")

        elif args.command == "link":
            api.link(args.src, args.dst, args.rel, args.weight)
            print_diagnostic(f"Linked: {args.src} --({args.rel})--> {args.dst}")

        elif args.command == "stats":
            stats = api.get_brain().get_stats()
            print("KIT STATUS\n")
            for scope in ["project", "global"]:
                data = stats.get(scope, {})
                print(f"{scope.capitalize()} Brain")
                print(f"  nodes: {data.get('nodes', 0)}")
                print(f"  edges: {data.get('edges', 0)}")
                print(f"  observations: {data.get('observations', 0)}\n")

        elif args.command == "doctor":
            from kit.cli.doctor import run_doctor

            run_doctor(
                api.get_brain(),
                args.mode,
                check_agents=args.check_agents,
                reset_cloud=args.reset_cloud,
            )

        elif args.command == "where":
            brain = api.get_brain()
            print(f"Brain: {brain.db_path}")
            print(f"Root:  {brain.root_path}")
            print(f"Scope: '{brain.get_normalized_scope()}'")

        elif args.command == "render":
            api.get_brain().render_context()
            print_diagnostic("AI context manifests regenerated.")

        elif args.command == "blame":
            records = api.get_blame(args.symbol)
            if not records:
                print_diagnostic(f"No architectural history found for symbol '{args.symbol}'.")
            else:
                print(f"Architectural Blame: {args.symbol}\n")
                for r in records:
                    author = r["agent_id"] or "unknown"
                    commit = f" [{r['commit_msg']}]" if r["commit_msg"] else ""
                    print(f"   * {r['created_at']} | {author}{commit}")
                    print(f"     Fact: {r['content']}\n")

        elif args.command == "watch":
            import json as json_lib

            try:
                for event in api.stream_events():
                    print(json_lib.dumps(event), flush=True)
            except KeyboardInterrupt:
                pass

        elif args.command == "preflight":
            import json as json_lib

            piped_diff = None
            piped_diff = read_stdin_fail_fast(timeout=FAST_TIMEOUT)

            result = api.preflight_check(args.message, args.strict, diff_text=piped_diff)

            if args.json:
                print(json_lib.dumps(result))
            else:
                score_str = f"{result['score']:.2f}"
                status = result["status"].upper()
                print(f"Cognitive Check: {status} (Score: {score_str})")

                if result["issues"]:
                    print("\nIssues Found:")
                    for issue in result["issues"]:
                        print(f"  - [{issue['type'].upper()}]: {issue['message']}")

                if result["suggestions"]:
                    print("\nSuggestions:")
                    for suggestion in result["suggestions"]:
                        print(f"  - {suggestion}")

                if result["status"] == "block":
                    sys.exit(1)
            sys.exit(0)

        elif args.command == "reflect":
            diff_text = ""
            if args.file:
                if not Path(args.file).exists():
                    print_diagnostic(f"Error: File {args.file} not found.")
                    sys.exit(1)
                with open(args.file, encoding="utf-8") as f:
                    diff_text = f.read()
            else:
                try:
                    diff_res = run_safe(["git", "diff", "--cached"], timeout=DEFAULT_TIMEOUT)
                    diff_text = diff_res.stdout
                    if not diff_text:
                        diff_res = run_safe(["git", "diff", "HEAD"], timeout=DEFAULT_TIMEOUT)
                        diff_text = diff_res.stdout
                except (RuntimeError, FileNotFoundError):
                    print_diagnostic("Error: No file provided and no staged git changes found.")
                    sys.exit(1)

            if not diff_text:
                print_diagnostic("No changes detected for reflection.")
                sys.exit(0)

            scope = args.scope
            if getattr(args, "here", False):
                scope = api.get_brain().get_normalized_scope()

            report = api.reflect(diff_text, scope=scope)

            if args.json:
                import json

                print(json.dumps(vars(report), indent=2))
            else:
                print("\nCognitive Reflection")
                color = "OK" if report.score > 0.8 else "WARN"
                if report.status == "BLOCK":
                    color = "BLOCK"

                print(f"\nScore: {report.score:.1f} ({report.status}) {color}")

                if report.confirmations:
                    print("\nConfirmations:")
                    for confirmation in report.confirmations:
                        res = report.resolutions.get(confirmation)
                        if res and "Overrides" in res.reason:
                            print(
                                f"  - {confirmation} aligns with previous decisions (Arbitrated: {res.reason} [Conf: {res.confidence:.1f}])"
                            )
                        else:
                            print(f"  - {confirmation} aligns with previous decisions")

                if report.gaps:
                    print("\nGaps (Missing from memory):")
                    for gap in report.gaps:
                        print(f"  - {gap}")

                if report.drifts:
                    print("\nDrifts (Scope mismatch):")
                    for drift in report.drifts:
                        res = report.resolutions.get(drift)
                        reason = f" ({res.reason})" if res else ""
                        print(f"  - {drift}{reason}")

                if report.violations:
                    print("\nViolations (Invariant broken):")
                    for violation in report.violations:
                        res = report.resolutions.get(violation)
                        if res and "CONSTITUTIONAL" in res.reason:
                            print(f"  - {violation} -> BLOCK {res.reason}")
                        else:
                            reason = f" -> {res.reason}" if res else ""
                            print(f"  - {violation}{reason}")

                if report.suggestions:
                    print("\nSuggestions:")
                    for suggestion in report.suggestions:
                        print(f"  - {suggestion}")

                print("")

            mode = args.mode
            if args.strict:
                mode = "strict"

            if mode == "strict" and report.status == "BLOCK":
                sys.exit(1)
            if mode == "advisory" and report.status == "BLOCK":
                print_diagnostic("System is in ADVISORY mode: Block bypassed.")

        elif args.command == "label":
            from kit.cli import auto_route

            # Log corrective feedback for v1.2.4 Adaptive Loop
            feedback = {
                "ts": datetime.now(UTC).isoformat(),
                "type": "FEEDBACK",
                "obs_id": args.id,
                "correct_label": args.correct,
            }
            auto_route.log(feedback)
            print_diagnostic(f"Feedback logged: Observation {args.id} -> {args.correct}. v1.2.4 Trainer will use this.")

    except Exception as e:
        print_diagnostic(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
