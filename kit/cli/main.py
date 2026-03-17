import sys
import argparse
import random
import subprocess
import shutil
import os
from pathlib import Path


def main():
    # Habit Loop: Default to 'recall' if no command is given
    if len(sys.argv) == 1:
        sys.argv.append("recall")

    parser = argparse.ArgumentParser(
        description="SAMBrain CLI v2.0 - The Elite AI Memory Kernel",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", help="Path to the project database (overrides default)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: init
    init_p = subparsers.add_parser("init", help="Initialize a new .kit memory space in the current directory")

    # Command: learn
    learn_p = subparsers.add_parser("learn", help="Ingest a new observation")
    learn_p.add_argument("--uid", help="Node UID (node identity)")
    learn_p.add_argument("--kind", default="observation", help="Node kind (e.g., concept, bug, arch)")
    learn_p.add_argument("--content", help="The observation to remember")
    learn_p.add_argument("--importance", type=float, default=1.0, help="Importance [0.1 - 1.0]")
    learn_p.add_argument("--supersede", type=int, help="ID of the observation to supersede")
    learn_p.add_argument(
        "--tag",
        choices=["invariant", "decision", "preference"],
        default="decision",
        help="Fact alignment tag"
    )
    learn_p.add_argument(
        "--layer",
        "-l",
        choices=["working", "episodic", "semantic", "procedural"],
        default="episodic",
        help="Cognitive layer"
    )
    learn_p.add_argument("--global", action="store_true", dest="to_global", help="Learn into Global Brain")
    learn_p.add_argument("--namespace", default="shared", help="Namespace (e.g., project, agent:name)")
    learn_p.add_argument("--scope", help="Optional explicit scope (folder path)")
    learn_p.add_argument("--agent-id", help="Explicit Agent ID for attribution")
    learn_p.add_argument("--symbol", help="Anchor fact to a specific code symbol (AST node)")
    learn_p.add_argument("--hash", help="Structural hash of the symbol")

    # Command: search
    search_p = subparsers.add_parser("search", help="Hybrid FTS5 keyword search")
    search_p.add_argument("query", help="Keyword or phrase to search for")
    search_p.add_argument("--limit", type=int, default=15)
    search_p.add_argument("--at", help="Temporal snapshot (YYYY-MM-DD HH:MM:SS)")
    search_p.add_argument("--agent-id", help="Agent ID for recall boost")
    search_p.add_argument("--fast", action="store_true", help="Fast mode (skip heavy ranking)")

    # Command: recall
    recall_p = subparsers.add_parser("recall", help="Recall ranked context (Project + Global)")
    recall_p.add_argument("entities", nargs="*", help="Entity UIDs")
    recall_p.add_argument("--limit", type=int, default=15)
    recall_p.add_argument("--at", help="Temporal snapshot")
    recall_p.add_argument("--agent-id", help="Agent ID for recall boost")
    recall_p.add_argument("--here", action="store_true", help="Filter/Boost by current directory scope")
    recall_p.add_argument("--symbol", help="Recall context specifically for this code symbol")
    recall_p.add_argument("--fast", action="store_true", help="Fast mode (skip heavy ranking)")

    # Command: context
    context_p = subparsers.add_parser("context", help="Alias for recall --here (Project context awareness)")
    context_p.add_argument("--limit", type=int, default=15)
    context_p.add_argument("--at", help="Temporal snapshot")
    context_p.add_argument("--agent-id", help="Agent ID for recall boost")
    context_p.add_argument("--symbol", help="Recall context specifically for this code symbol")
    context_p.add_argument("--fast", action="store_true", help="Fast mode (skip heavy ranking)")

    # Command: blame
    blame_p = subparsers.add_parser("blame", help="Show architectural causality chain for a symbol")
    blame_p.add_argument("symbol", help="The code symbol (function, class, etc.)")

    # Command: where
    subparsers.add_parser("where", help="Show current memory context and brain path")

    # Command: link
    link_p = subparsers.add_parser("link", help="Create a semantic edge between two nodes")
    link_p.add_argument("--src", required=True)
    link_p.add_argument("--dst", required=True)
    link_p.add_argument("--rel", required=True, help="Relation type (e.g., DEPENDS_ON)")
    link_p.add_argument("--weight", type=float, default=1.0)

    # Command: stats
    subparsers.add_parser("stats", help="Show AI Kernel statistics (Hybrid)")

    # Command: bump
    bump_p = subparsers.add_parser("bump", help="Reinforce a memory (increment access count)")
    bump_p.add_argument("id", type=int, help="Observation ID")

    # Command: promote
    promote_p = subparsers.add_parser("promote", help="Promote episodic memories to semantic")
    promote_p.add_argument("--threshold", type=int, default=5, help="Access count threshold")

    # Command: doctor
    doctor_p = subparsers.add_parser("doctor", help="System diagnostics & Cognitive Hygiene")
    doctor_p.add_argument("--mode", choices=["safe", "aggressive"], default="safe", help="Hygiene strictness level")

    # Command: render
    subparsers.add_parser("render", help="Force regenerate AI context files (.kit/context, AGENTS.md)")

    # Command: watch
    watch_p = subparsers.add_parser("watch", help="Stream cognitive events in real-time")
    watch_p.add_argument("--json", action="store_true", help="Output raw JSON stream")

    # Command: preflight
    preflight_p = subparsers.add_parser("preflight", help="Run cognitive governance checks before committing")
    preflight_p.add_argument("-m", "--message", type=str, required=True, help="The commit message to evaluate")
    preflight_p.add_argument("--strict", action="store_true", help="Treat warnings as blocking errors (for CI)")
    preflight_p.add_argument("--json", action="store_true", help="Output raw JSON format")

    # Plugin Delegation Logic (Git-style) - Checked BEFORE argparse for unknown commands
    known_commands = ["init", "learn", "search", "recall", "context", "where", "link", "stats", "bump", "promote", "doctor", "render", "watch", "preflight"]
    
    if len(sys.argv) > 1:
        potential_cmd = sys.argv[1]
        
        # If it's not a flag and not a known command, check for plugin
        if not potential_cmd.startswith("-") and potential_cmd not in known_commands:
            plugin_name = f"kit-{potential_cmd}"
            plugin_path = shutil.which(plugin_name)
            
            if plugin_path:
                # Shift argv: [kit, vantage, check] -> [kit-vantage, check]
                plugin_args = [plugin_path] + sys.argv[2:]
                try:
                    # Use shell=True on Windows to support .bat/.cmd files
                    # Pass through stdin/stdout by default
                    result = subprocess.run(plugin_args, shell=(os.name == 'nt'))
                    sys.exit(result.returncode)
                except Exception as e:
                    print(f"❌ Error executing plugin '{plugin_name}': {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                # Let argparse handle the "unknown command" error later if no plugin found
                pass

    args = parser.parse_args()

    # Lazy Import for speed
    import kit.api as api

    # Initialize Kernel
    db_path = Path(args.db).absolute() if args.db else None
    api.init_kernel(db_path)

    def print_diagnostic(msg: object) -> None:
        print(msg, file=sys.stderr)

    is_tty = sys.stdout.isatty()
    current_context = Path.cwd().name

    try:
        if args.command == "init":
            from kit.api import resolve_paths
            _, project_db, root_path = resolve_paths()
            kit_dir = root_path / ".kit"
            
            agents_md = root_path / "AGENTS.md"
            if not agents_md.exists():
                agents_md.write_text("# Project Intelligence\n\nThis repository's architectural constraints and memory are managed by `.kit`.\n\n<!-- GENERATED BY KIT START -->\n<!-- GENERATED BY KIT END -->\n", encoding="utf-8")
                print_diagnostic(f"✅ Created {agents_md.name}")

            gitignore = root_path / ".gitignore"
            if gitignore.exists() or root_path.joinpath(".git").exists():
                content = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
                if ".kit/brain.db-*" not in content:
                    with open(gitignore, "a", encoding="utf-8") as f:
                        f.write("\n# .kit Memory Store\n.kit/brain.db-*\n.kit/brain.db.bak\n")
                    print_diagnostic(f"✅ Updated {gitignore.name} to ignore SQLite WAL/SHM files")

            print_diagnostic(f"🧠 .kit initialized successfully in {kit_dir}")
            print_diagnostic("🚀 Run `kit learn --tag invariant 'Rule 1'` to start building your cognitive memory!")

        elif args.command == "learn":
            content = args.content
            if not sys.stdin.isatty():
                piped = sys.stdin.read().strip()
                content = f"{content}\n{piped}".strip() if content else piped

            if not content:
                print_diagnostic("❌ Error: No content provided.")
                sys.exit(1)

            uid = args.uid or current_context
            
            # API call now supports to_global and supersede
            fact_id = api.get_brain().learn(
                uid=uid,
                kind=args.kind,
                content=content,
                importance=args.importance,
                layer=args.layer,
                to_global=args.to_global,
                supersede_id=args.supersede,
                namespace=args.namespace,
                scope=args.scope,
                agent_id=args.agent_id,
                symbol=args.symbol,
                structural_hash=args.hash,
                tag=args.tag
            )
            target = "Global" if args.to_global else "Project"
            print_diagnostic(f"✅ Learned: [{uid}] -> {target} Brain (ID: {fact_id})")

        elif args.command == "search":
            is_fast = getattr(args, "fast", False)
            memories = api.search(args.query, limit=args.limit, at=args.at, agent_id=args.agent_id, fast=is_fast)
            if is_tty:
                print_diagnostic(f"🔍 Hybrid Search results for '{args.query}':\n")
            
            if not memories:
                print_diagnostic("No matches found.")
            else:
                for m in memories:
                    print(f"• [ID:{m.id}][{m.brain_source}:{m.node_uid}] {m.content} (score: {m.score:.2f})")

        elif args.command == "recall" or args.command == "context":
            entities = args.entities if args.command == "recall" else []
            if args.command == "recall" and not entities:
                entities = [current_context]
            
            is_here = getattr(args, "here", False) or args.command == "context"
            is_fast = getattr(args, "fast", False)
            memories = api.recall(entities, limit=args.limit, at=args.at, agent_id=args.agent_id, here=is_here, symbol=args.symbol, fast=is_fast)
            
            if is_tty:
                scope_str = f" [Scope: {api.get_brain().get_normalized_scope()}]" if is_here else ""
                print_diagnostic(f"🧠 Recalled context for {entities or 'current scope'}{scope_str}:\n")
            
            if not memories:
                print_diagnostic("No relevant memories found.")
            else:
                for m in memories:
                    print(f"• [ID:{m.id}][{m.brain_source}:{m.node_uid}][{m.layer}:{m.namespace}][{m.created_at}][{m.importance:.1f}] {m.content}")

        elif args.command == "bump":
            if api.touch(args.id):
                print_diagnostic(f"✅ Memory {args.id} reinforced.")
            else:
                print_diagnostic(f"❌ Failed to reinforce memory {args.id}.")

        elif args.command == "promote":
            count = api.promote(args.threshold)
            print_diagnostic(f"🚀 Promoted {count} memories to Semantic layer (Threshold: {args.threshold}).")

        elif args.command == "link":
            api.link(args.src, args.dst, args.rel, args.weight)
            print_diagnostic(f"✅ Linked: {args.src} --({args.rel})--> {args.dst}")

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
            run_doctor(api.get_brain(), args.mode)

        elif args.command == "where":
            brain = api.get_brain()
            print(f"Brain: {brain.db_path}")
            print(f"Root:  {brain.root_path}")
            print(f"Scope: '{brain.get_normalized_scope()}'")

        elif args.command == "render":
            api.get_brain().render_context()
            print_diagnostic("✅ AI Context manifests regenerated.")

        elif args.command == "blame":
            records = api.get_blame(args.symbol)
            if not records:
                print_diagnostic(f"No architectural history found for symbol '{args.symbol}'.")
            else:
                print(f"🕵️  Architectural Blame: {args.symbol}\n")
                for r in records:
                    author = r['agent_id'] or "unknown"
                    commit = f" [{r['commit_msg']}]" if r['commit_msg'] else ""
                    print(f"   • {r['created_at']} | {author}{commit}")
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
            result = api.preflight_check(args.message, args.strict)
            
            if args.json:
                print(json_lib.dumps(result))
            else:
                score_str = f"{result['score']:.2f}"
                status = result['status'].upper()
                if status == "PASS":
                    print(f"✅ Cognitive Check: {status} (Score: {score_str})")
                elif status == "WARN":
                    print(f"⚠️ Cognitive Check: {status} (Score: {score_str})")
                else:
                    print(f"❌ Cognitive Check: {status} (Score: {score_str})")
                
                if result['issues']:
                    print("\n🔍 Issues Found:")
                    for i in result['issues']:
                        print(f"  - [{i['type'].upper()}]: {i['message']}")
                
                if result['suggestions']:
                    print("\n💡 Suggestions:")
                    for s in result['suggestions']:
                        print(f"  - {s}")
            
            # Exit codes: 0 = PASS, 0 = WARN (if not strict), 2 = BLOCK
            if result['status'] == "block":
                sys.exit(2)
            sys.exit(0)

    except Exception as e:
        print_diagnostic(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
