import sys
import argparse
import random
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

    # Command: learn
    learn_p = subparsers.add_parser("learn", help="Ingest a new observation")
    learn_p.add_argument("--uid", help="Node UID (node identity)")
    learn_p.add_argument("--kind", default="observation", help="Node kind (e.g., concept, bug, arch)")
    learn_p.add_argument("--content", help="The observation to remember")
    learn_p.add_argument("--importance", type=float, default=1.0, help="Importance [0.1 - 1.0]")
    learn_p.add_argument(
        "--layer",
        "-l",
        choices=["working", "episodic", "semantic", "procedural"],
        default="episodic",
        help="Cognitive layer"
    )
    learn_p.add_argument("--global", action="store_true", dest="to_global", help="Learn into Global Brain")

    # Command: search
    search_p = subparsers.add_parser("search", help="Hybrid FTS5 keyword search")
    search_p.add_argument("query", help="Keyword or phrase to search for")
    search_p.add_argument("--limit", type=int, default=15)
    search_p.add_argument("--at", help="Temporal snapshot (YYYY-MM-DD HH:MM:SS)")

    # Command: recall
    recall_p = subparsers.add_parser("recall", help="Recall ranked context (Project + Global)")
    recall_p.add_argument("entities", nargs="*", help="Entity UIDs")
    recall_p.add_argument("--limit", type=int, default=15)
    recall_p.add_argument("--at", help="Temporal snapshot")

    # Command: link
    link_p = subparsers.add_parser("link", help="Create a semantic edge between two nodes")
    link_p.add_argument("--src", required=True)
    link_p.add_argument("--dst", required=True)
    link_p.add_argument("--rel", required=True, help="Relation type (e.g., DEPENDS_ON)")
    link_p.add_argument("--weight", type=float, default=1.0)

    # Command: stats
    subparsers.add_parser("stats", help="Show AI Kernel statistics (Hybrid)")

    # Command: doctor
    subparsers.add_parser("doctor", help="System diagnostics")

    args = parser.parse_args()

    # Lazy Import for speed
    from kit import api

    # Initialize Kernel
    db_path = Path(args.db).absolute() if args.db else None
    api.init_kernel(db_path)

    def print_diagnostic(msg: object) -> None:
        print(msg, file=sys.stderr)

    is_tty = sys.stdout.isatty()
    current_context = Path.cwd().name

    try:
        if args.command == "learn":
            content = args.content
            if not sys.stdin.isatty():
                piped = sys.stdin.read().strip()
                content = f"{content}\n{piped}".strip() if content else piped

            if not content:
                print_diagnostic("❌ Error: No content provided.")
                sys.exit(1)

            uid = args.uid or current_context
            
            # API call now supports to_global
            fact_id = api.get_brain().learn(
                uid=uid,
                kind=args.kind,
                content=content,
                importance=args.importance,
                layer=args.layer,
                to_global=args.to_global
            )
            target = "Global" if args.to_global else "Project"
            print_diagnostic(f"✅ Learned: [{uid}] -> {target} Brain (ID: {fact_id})")

        elif args.command == "search":
            memories = api.search(args.query, limit=args.limit, at=args.at)
            if is_tty:
                print_diagnostic(f"🔍 Hybrid Search results for '{args.query}':\n")
            
            if not memories:
                print_diagnostic("No matches found.")
            else:
                for m in memories:
                    print(f"• [{m.brain_source}:{m.node_uid}] {m.content} (score: {m.score:.2f})")

        elif args.command == "recall":
            entities = args.entities or [current_context]
            memories = api.recall(entities, limit=args.limit, at=args.at)
            
            if is_tty:
                print_diagnostic(f"🧠 Recalled context for {entities}:\n")
            
            if not memories:
                print_diagnostic("No relevant memories found.")
            else:
                for m in memories:
                    print(f"• [{m.brain_source}:{m.node_uid}] {m.content}")

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
            brain = api.get_brain()
            print_diagnostic("🏥 AI Kernel Health Check")
            print_diagnostic(f"Project DB: {brain.db_path}")
            print_diagnostic(f"Global DB: {brain.global_db_path}")
            print_diagnostic("Status: OK")

    except Exception as e:
        print_diagnostic(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
