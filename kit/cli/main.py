import sys
import argparse
import random
from pathlib import Path

def main():
    # Habit Loop: Default to 'recall' if no command is given
    # This means just typing 'kit' shows recent memories.
    if len(sys.argv) == 1:
        sys.argv.append("recall")

    parser = argparse.ArgumentParser(
        description="SAMBrain CLI - The Elite Agent Memory Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", help="Path to the memory database (default: auto-resolve)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: learn
    learn_p = subparsers.add_parser("learn", help="Ingest a new fact")
    learn_p.add_argument("--uid", help="Entity UID (defaults to current directory name)")
    learn_p.add_argument("--kind", default="concept", help="Entity kind (e.g., bug, arch, task)")
    learn_p.add_argument("--content", help="The fact to remember (can also be piped via stdin)")
    learn_p.add_argument("--weight", type=float, default=0.5, help="Importance weight [0.1 - 1.0]")
    learn_p.add_argument("--replaces", type=int, help="ID of a fact to supersede")

    # Command: recall
    recall_p = subparsers.add_parser("recall", help="Recall ranked context (includes 1-hop expansion)")
    recall_p.add_argument("--entities", nargs="+", help="Entity UIDs (defaults to current directory name)")
    recall_p.add_argument("--limit", type=int, default=15, help="Max number of items to return")

    # Command: link
    link_p = subparsers.add_parser("link", help="Create a semantic link between two entities")
    link_p.add_argument("--src", required=True, help="Source entity UID")
    link_p.add_argument("--dst", required=True, help="Target entity UID")
    link_p.add_argument("--rel", required=True, help="Relation type (e.g., USES, DEPENDS_ON)")
    link_p.add_argument("--weight", type=float, default=1.0)
    
    # Command: export
    export_p = subparsers.add_parser("export", help="Export context as XML/Markdown for LLM prompts")
    export_p.add_argument("--entities", nargs="+", required=True, help="Entity UIDs")
    export_p.add_argument("--limit", type=int, default=10)
    export_p.add_argument("--budget", type=int, default=1000, help="Token budget approximation")
    
    # Command: doctor
    subparsers.add_parser("doctor", help="System diagnostics & health check")
    
    # Command: stats
    subparsers.add_parser("stats", help="Show brain statistics")

    args = parser.parse_args()

    # Lazy Import for speed: Don't load the heavy logic until we know we need it
    from kit import api
    
    # Initialize Kernel with auto-resolution
    db_path = Path(args.db).absolute() if args.db else None
    api.init_kernel(db_path)

    # Habit Loop: Contextual Auto-Discovery
    current_context = Path.cwd().name
    
    is_tty = sys.stdout.isatty()

    def print_diagnostic(msg):
        """Prints info/success to stderr to keep stdout clean for data piping."""
        print(msg, file=sys.stderr)

    def print_hint(cmd):
        """Randomly suggests a power-user tip."""
        if not is_tty or random.random() > 0.2:
            return
        hints = {
            "learn": ["tip: run 'kit recall' to see your memories", "tip: search with 'kit recall | grep <word>'"],
            "recall": ["tip: fuzzy search: 'kit recall | fzf'"]
        }
        if cmd in hints:
            print(f"\n💡 {random.choice(hints[cmd])}", file=sys.stderr)
    
    try:
        if args.command == "learn":
            # stdin-first logic
            content = args.content
            if not sys.stdin.isatty():
                piped = sys.stdin.read().strip()
                content = f"{content}\n{piped}".strip() if content else piped
            
            if not content:
                print_diagnostic("❌ Error: No content provided. Use --content or pipe from stdin.")
                sys.exit(1)

            uid = args.uid or current_context
            fact_id = api.learn(
                entity_uid=uid,
                kind=args.kind,
                content=content,
                importance=args.weight,
                replaces_id=args.replaces,
            )
            print_diagnostic(f"✅ Learned: Fact ID {fact_id} credited to [{uid}]")
            print_hint("learn")

        elif args.command == "recall":
            entities = args.entities or [current_context]
            nodes = api.recall(entities, limit=args.limit)
            
            if is_tty:
                print_diagnostic(f"🧠 Memories for [{', '.join(entities)}]:\n")
            
            if not nodes:
                if is_tty:
                    print_diagnostic(f"No relevant memories found for [{', '.join(entities)}].")
            else:
                for n in nodes:
                    if is_tty:
                        print(f"• {n.content}")
                    else:
                        print(n.content)
            print_hint("recall")

        elif args.command == "link":
            api.link_entities(args.src, args.dst, args.rel, args.weight)
            print_diagnostic(f"✅ Linked: {args.src} --({args.rel})--> {args.dst}")

        elif args.command == "export":
            prompt = api.export_prompt(args.entities, limit=args.limit, budget=args.budget)
            print(prompt) # Data goes to stdout
            
        elif args.command == "doctor":
            brain = api.get_brain()
            print_diagnostic("🏥 SAMBrain Health Check")
            print_diagnostic(f"Location: {brain.db_path}")
            print_diagnostic(f"Size: {brain.db_path.stat().st_size / 1024:.2f} KB")
            print_diagnostic("Status: OK")
            
        elif args.command == "stats":
            brain = api.get_brain()
            stats = brain.get_stats()
            print_diagnostic("📊 SAMBrain Statistics")
            print_diagnostic(f"Entities: {stats['entities']}")
            print_diagnostic(f"Facts: {stats['facts']} (Active: {stats['active_facts']})")
            print_diagnostic(f"Relations: {stats['relations']}")
            print_diagnostic(f"Lineage Links: {stats['lineage_links']}")

    except Exception as e:
        print_diagnostic(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
