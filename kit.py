#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from kit_adapters import AtlasAdapter, BrainAdapter


def parse_args():
    parser = argparse.ArgumentParser(description="Antigravity Memory Kit CLI (kit)")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    symbol_parser = subparsers.add_parser("symbol", help="Search unified symbols (Code + Docs)")
    symbol_parser.add_argument("query", help="Query string")
    symbol_parser.add_argument("--limit", type=int, default=10, help="Limit results per source")
    symbol_parser.add_argument("--include-private", action="store_true", help="Include private memory")
    symbol_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    callers_parser = subparsers.add_parser("callers", help="Find callsites for a code symbol")
    callers_parser.add_argument("symbol", help="Callee symbol name")
    callers_parser.add_argument("--limit", type=int, default=50, help="Limit callers")
    callers_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    snippet_parser = subparsers.add_parser("snippet", help="Read a source snippet around PATH:LINE")
    snippet_parser.add_argument("target", help="Snippet target in PATH:LINE format")
    snippet_parser.add_argument("--radius", type=int, default=10, help="Lines of context around the target line")
    snippet_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    context_parser = subparsers.add_parser("context", help="Read unified code context for a symbol")
    context_parser.add_argument("symbol", help="Symbol name")
    context_parser.add_argument("--callers-limit", type=int, default=5, help="Limit callers")
    context_parser.add_argument("--callees-limit", type=int, default=5, help="Limit callees")
    context_parser.add_argument("--radius", type=int, default=8, help="Lines of source context around the definition")
    context_parser.add_argument("--include-private", action="store_true", help="Include private memory")
    context_parser.add_argument("--doc-limit", type=int, default=5, help="Limit related docs")
    context_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    return parser.parse_args()


def main():
    args = parse_args()
    workspace_root = Path(os.environ.get("ANTIGRAVITY_WORKSPACE_ROOT", os.getcwd()))
    atlas = AtlasAdapter(workspace_root)

    if args.command == "symbol":
        brain = BrainAdapter(workspace_root)
        code_results = atlas.search(args.query, limit=args.limit)
        doc_results = brain.search(args.query, include_private=args.include_private, limit=args.limit)
        combined = code_results + doc_results
        payload = {"query": args.query, "results": combined}

        if args.json or not sys.stdout.isatty():
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            if not combined:
                print(f"No results found for '{args.query}'.")
                return

            print(f"--- Unified Symbol Search: '{args.query}' ---")
            for i, result in enumerate(combined, 1):
                icon = "[code]" if result["type"].startswith("code") else "[doc]"
                print(f"[{i}] {icon} {result['name']} ({result['kind']})")
                print(f"    Path:  {result['path']}")
                if result.get("line"):
                    print(f"    Line:  {result['line']}")
                if result.get("snippet"):
                    print(f"    Snippet: {result['snippet']}...")
                print("")
        return

    if args.command == "callers":
        results = atlas.callers(args.symbol, limit=args.limit)
        payload = {"query": args.symbol, "results": results}
        if args.json or not sys.stdout.isatty():
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            if not results:
                print(f"No callers found for '{args.symbol}'.")
                return
            print(f"--- Callers: '{args.symbol}' ---")
            for i, result in enumerate(results, 1):
                print(f"[{i}] {result['caller']}")
                print(f"    Path:  {result['path']}")
                print(f"    Line:  {result['line']}")
                print("")
        return

    if args.command == "snippet":
        result = atlas.snippet(args.target, radius=args.radius)
        payload = {"query": args.target, "results": [result]}
        if args.json or not sys.stdout.isatty():
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"--- Snippet: {result['path']}:{result['line']} ---")
            print(result["snippet"])
        return

    if args.command == "context":
        brain = BrainAdapter(workspace_root)
        context = atlas.get_unified_context(
            args.symbol,
            caller_limit=args.callers_limit,
            callee_limit=args.callees_limit,
            snippet_radius=args.radius,
        )
        context["docs"] = brain.get_unified_context(
            args.symbol,
            include_private=args.include_private,
            limit=args.doc_limit,
        )
        context["metrics"]["doc_count"] = len(context["docs"])
        payload = {"query": args.symbol, "results": [context]}
        if args.json or not sys.stdout.isatty():
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            definition = context.get("definition")
            if definition is None:
                print(f"No code context found for '{args.symbol}'.")
                return

            print(f"--- Context: '{args.symbol}' ---")
            print(f"Definition: {definition['name']} ({definition['kind']})")
            print(f"Path:       {definition['path']}:{definition['line']}")
            print(f"Callers:    {context['metrics']['caller_count']}")
            print(f"Callees:    {context['metrics']['callee_count']}")
            print(f"Docs:       {context['metrics']['doc_count']}")
            if context.get("snippet"):
                print("")
                print(context["snippet"]["snippet"])
        return

    print("Antigravity Memory Kit v0.1.0-phase7.5")
    print("Usage: kit symbol|callers|snippet|context ...")


if __name__ == "__main__":
    main()
