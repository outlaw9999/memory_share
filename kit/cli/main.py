import sys
import argparse
from pathlib import Path
from kit import api

def main():
    parser = argparse.ArgumentParser(
        description="SAMBrain CLI - The Elite Agent Memory Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", default="memory.db", help="Path to the memory database (default: memory.db)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: learn
    learn_p = subparsers.add_parser("learn", help="Ingest a new fact into memory")
    learn_p.add_argument("--uid", required=True, help="Entity UID (e.g., AuthService)")
    learn_p.add_argument("--kind", default="Concept", help="Entity kind (Component, Logic, etc.)")
    learn_p.add_argument("--content", required=True, help="Semantic content of the fact")
    learn_p.add_argument("--weight", type=float, default=0.5, help="Importance weight [0.1 - 1.0]")
    learn_p.add_argument("--replaces", type=int, help="ID of a fact to supersede (Immutable Ledger logic)")

    # Command: recall
    recall_p = subparsers.add_parser("recall", help="Recall ranked context (includes 1-hop expansion)")
    recall_p.add_argument("--entities", nargs="+", required=True, help="List of entity UIDs to recall")
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialize Kernel
    db_path = Path(args.db).absolute()
    api.init_kernel(db_path)

    try:
        if args.command == "learn":
            fact_id = api.learn(
                entity_uid=args.uid,
                kind=args.kind,
                content=args.content,
                importance=args.weight,
                replaces_id=args.replaces
            )
            print(f"✅ Learned: Fact ID {fact_id} credited to [{args.uid}]")

        elif args.command == "recall":
            nodes = api.recall(args.entities, limit=args.limit)
            if not nodes:
                print("No relevant memories found.")
            for n in nodes:
                print(f"[{n.entity_uid}] (Score: {n.score:.4f}, Dist: {n.distance}) -> {n.content}")

        elif args.command == "link":
            api.link_entities(args.src, args.dst, args.rel, args.weight)
            print(f"✅ Linked: {args.src} --({args.rel})--> {args.dst}")

        elif args.command == "export":
            prompt = api.export_prompt(args.entities, limit=args.limit, budget=args.budget)
            print(prompt)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
