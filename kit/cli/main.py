import sys
import argparse
from pathlib import Path
from kit import api

def main():
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
    learn_p.add_argument("--content", required=True, help="Semantic content of the fact")
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

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialize Kernel with auto-resolution
    db_path = Path(args.db).absolute() if args.db else None
    api.init_kernel(db_path)

    # Habit Loop: Contextual Auto-Discovery
    current_context = Path.cwd().name
    
    try:
        if args.command == "learn":
            uid = args.uid or current_context
            fact_id = api.learn(
                entity_uid=uid,
                kind=args.kind,
                content=args.content,
                importance=args.weight,
                replaces_id=args.replaces,
            )
            print(f"✅ Learned: Fact ID {fact_id} credited to [{uid}]")

        elif args.command == "recall":
            entities = args.entities or [current_context]
            nodes = api.recall(entities, limit=args.limit)
            if not nodes:
                print(f"No relevant memories found for [{', '.join(entities)}].")
            for n in nodes:
                print(n.content)

        elif args.command == "link":
            api.link_entities(args.src, args.dst, args.rel, args.weight)
            print(f"✅ Linked: {args.src} --({args.rel})--> {args.dst}")

        elif args.command == "export":
            prompt = api.export_prompt(args.entities, limit=args.limit, budget=args.budget)
            print(prompt)
            
        elif args.command == "doctor":
            brain = api.get_brain()
            print("🏥 SAMBrain Health Check")
            print(f"Location: {brain.db_path}")
            print(f"Size: {brain.db_path.stat().st_size / 1024:.2f} KB")
            print("Status: OK")
            
        elif args.command == "stats":
            brain = api.get_brain()
            stats = brain.get_stats()
            print("📊 SAMBrain Statistics")
            print(f"Entities: {stats['entities']}")
            print(f"Facts: {stats['facts']} (Active: {stats['active_facts']})")
            print(f"Relations: {stats['relations']}")
            print(f"Lineage Links: {stats['lineage_links']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
