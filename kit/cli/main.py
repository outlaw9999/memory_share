import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from kit.core.graph_store import GraphStore
from kit.index.ast_indexer import V1ASTIndexer
from kit.services.cognitive_router import CognitiveRouter


def main() -> int:
    parser = argparse.ArgumentParser(description=".kit V1: Agent Knowledge Kernel")
    subparsers = parser.add_subparsers(dest="command")

    # Command: index
    index_parser = subparsers.add_parser("index", help="Index codebase into Graph")
    index_parser.add_argument("path", nargs="?", default=".", help="Path to codebase")
    index_parser.add_argument("--full", action="store_true", help="Force full re-index")

    # Command: explain
    explain_parser = subparsers.add_parser("explain", help="Explain code logic")
    explain_parser.add_argument("query", help="Natural language query")

    # Command: hotspots
    hotspots_parser = subparsers.add_parser(
        "hotspots", help="Identify critical code components"
    )
    hotspots_parser.add_argument(
        "--limit", type=int, default=10, help="Number of hotspots to show"
    )
    hotspots_parser.add_argument(
        "--json", action="store_true", help="Output as JSON (pretty)"
    )
    hotspots_parser.add_argument(
        "--compact",
        action="store_true",
        help="Output as compact JSON (token efficient)",
    )

    # Command: doctor
    doctor_parser = subparsers.add_parser(
        "doctor", help="Audit architecture health and integrity"
    )
    doctor_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Command: why
    why_parser = subparsers.add_parser(
        "why", help="Explain architectural significance of a symbol"
    )
    why_parser.add_argument("symbol", help="Symbol name to explain")
    why_parser.add_argument(
        "--offline", action="store_true", help="Use deterministic mode (no LLM)"
    )
    why_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Initialize core components
    store = GraphStore()

    if args.command == "index":
        path = args.path
        print(f"[*] Indexing {path}...")
        indexer = V1ASTIndexer(store)

        if args.full:
            print("[!] Full re-index requested - deleting existing data...")

        indexer.index_repo(path)
        print("[OK] Indexing complete.")
        return 0

    if args.command == "hotspots":
        from kit.analysis.importance import GraphRankEngine

        ranker = GraphRankEngine(store)
        scores = ranker.compute_importance(iterations=10)

        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[
            : args.limit
        ]

        if args.json:
            print(json.dumps(sorted_scores, indent=2))
        elif args.compact:
            print(json.dumps(sorted_scores))
        else:
            print("--- Top Hotspots ---")
            for symbol_id, score in sorted_scores:
                print(f"  {score:.4f} (id={symbol_id})")
        return 0

    if args.command == "doctor":
        from kit.analysis.integrity import ArchitectureDoctor

        doctor = ArchitectureDoctor(store)
        report = doctor.diagnose()

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("--- Architecture Health ---")
            print(f"Healthy: {report['healthy']}")
            for issue in report["issues"]:
                print(f"  ! {issue}")
        return 0

    if args.command == "why":
        from kit.query.reasoning import ReasoningEngine

        engine = ReasoningEngine(store)
        result = engine.why(args.symbol, offline=args.offline)

        if args.json:
            print(json.dumps({"symbol": args.symbol, "explanation": result}, indent=2))
        else:
            print(result)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
