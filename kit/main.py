#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

# Package imports
from .indexer import AtlasIndexer
from .graph_store import GraphStore
from .scanner import Scanner
from .kernel import main as kernel_main

# Constants
ENGINE_VERSION = "v1.1.0"
CLI_VERSION = "v1.1.0"
WORKSPACE_ROOT = Path(os.environ.get("ANTIGRAVITY_WORKSPACE_ROOT", os.getcwd()))
DB_PATH = WORKSPACE_ROOT / ".antigravity" / "atlas" / "atlas.db"
QUERIES_DIR = WORKSPACE_ROOT / ".antigravity" / "queries"

# Stone Metadata
STONES_METADATA = {
    "cycles": {"category": "primitive", "purpose": "Detect circular dependencies", "confidence": "HIGH"},
    "god_modules": {"category": "primitive", "purpose": "Detect high fan-out modules", "confidence": "HIGH"},
    "architecture": {"category": "primitive", "purpose": "Infer and validate layer architecture", "confidence": "MEDIUM"},
    "entropy": {"category": "primitive", "purpose": "Measure call graph coupling", "confidence": "MEDIUM"},
    "gravity": {"category": "primitive", "purpose": "Detect dependency concentration", "confidence": "MEDIUM"},
    "hotspots": {"category": "primitive", "purpose": "Find high-risk modules", "confidence": "HIGH"},
    "choke_points": {"category": "primitive", "purpose": "Detect bottleneck modules", "confidence": "MEDIUM"},
    "dead_code": {"category": "primitive", "purpose": "Find unreachable symbols", "confidence": "HIGH"},
    "graph_health": {"category": "primitive", "purpose": "Assess graph completeness", "confidence": "MEDIUM"},
    "utility_hubs": {"category": "primitive", "purpose": "Distinguish utilities from orchestrators", "confidence": "MEDIUM"},
    "impact": {"category": "advanced", "purpose": "Estimate change blast radius", "confidence": "MEDIUM"},
    "domains": {"category": "advanced", "purpose": "Understand module organization", "confidence": "MEDIUM"},
    "doctor": {"category": "orchestrator", "purpose": "Unified health report", "confidence": "HIGH"},
    "drift": {"category": "orchestrator", "purpose": "Governance violations", "confidence": "HIGH"}
}

ALL_STONES = list(STONES_METADATA.keys())

def run_sql(query_name, params=None, timeout=30):
    query_file = QUERIES_DIR / "stones" / f"{query_name}.sql"
    if not query_file.exists():
        query_file = QUERIES_DIR / f"{query_name}.sql"
    
    if not query_file.exists():
        print(f"Error: Query Stone '{query_name}' not found.", file=sys.stderr)
        sys.exit(1)
    
    query_text = query_file.read_text()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=float(timeout))
        cur = conn.cursor()
        cur.execute(query_text, params or [])
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except:
                return row[0]
        return {}
    except Exception as e:
        print(f"Error executing SQL Stone '{query_name}': {e}", file=sys.stderr)
        sys.exit(1)

def cmd_init(args):
    atlas_dir = WORKSPACE_ROOT / ".antigravity" / "atlas"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    QUERIES_DIR.mkdir(parents=True, exist_ok=True)
    
    gitignore = WORKSPACE_ROOT / ".gitignore"
    line_to_add = ".antigravity/\n"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".antigravity/" not in content:
            with open(gitignore, "a") as f:
                f.write("\n# Antigravity Data\n" + line_to_add)
    else:
        gitignore.write_text("# Antigravity Data\n" + line_to_add)
    print(f"Initialized .kit infrastructure at {WORKSPACE_ROOT}/.antigravity/")

def cmd_index(args):
    print(f"Indexing codebase at {WORKSPACE_ROOT}...")
    import time
    start_time = time.time()
    store = GraphStore(DB_PATH)
    conn = store.conn
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    
    indexer = AtlasIndexer(workspace_root=str(WORKSPACE_ROOT), graph_store=store)
    scanner = Scanner()
    py_files = list(WORKSPACE_ROOT.rglob("*.py"))
    processed_count = 0
    
    try:
        for py_file in py_files:
            if ".antigravity" in str(py_file) or ".git" in str(py_file) or "venv" in str(py_file):
                continue
            symbols = scanner.scan_file(py_file)
            calls = scanner.scan_calls(py_file)
            store.update_file(py_file, symbols, calls)
            processed_count += 1
        conn.commit()
        conn.execute("VACUUM;")
    except Exception as e:
        conn.rollback()
        print(f"Index failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Indexed {processed_count} files in {time.time() - start_time:.2f}s.")

def cmd_doctor(args):
    timeout = getattr(args, 'timeout', 30)
    health = run_sql("doctor", timeout=timeout)
    drift = run_sql("drift", timeout=timeout)
    print(json.dumps({"doctor_report": health, "governance_report": drift}, indent=2))

def main():
    parser = argparse.ArgumentParser(description=f"Antigravity .kit CLI {CLI_VERSION}")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("init", help="Initialize .kit infrastructure")
    subparsers.add_parser("index", help="High-performance codebase indexing")
    subparsers.add_parser("stones", help="List all available diagnostic stones")
    
    query_parser = subparsers.add_parser("query", help="Execute a diagnostic stone")
    query_parser.add_argument("stone", help="Stone name")
    query_parser.add_argument("--timeout", type=int, default=30)
    
    doctor_parser = subparsers.add_parser("doctor", help="Orchestrator report")
    doctor_parser.add_argument("--timeout", type=int, default=30)
    
    # Kernel commands (delegated)
    subparsers.add_parser("symbol", help="Search symbols")
    subparsers.add_parser("context", help="Get symbol context")
    subparsers.add_parser("impact", help="Blast radius analysis")
    subparsers.add_parser("callers", help="Find callers")
    subparsers.add_parser("snippet", help="Read snippet")
    subparsers.add_parser("related", help="Explore nearby code")
    subparsers.add_parser("graph", help="Symbol graph view")

    args, unknown = parser.parse_known_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "stones":
        print(json.dumps(STONES_METADATA, indent=2))
    elif args.command == "query":
        result = run_sql(args.stone, timeout=args.timeout)
        print(json.dumps({"stone": args.stone, "results": result}, indent=2))
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command in ["symbol", "context", "impact", "callers", "snippet", "related", "graph"]:
        # Re-parse sys.argv to pass to kernel_main
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        kernel_main()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
