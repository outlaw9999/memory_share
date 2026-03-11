import argparse
import sqlite3
import os
from pathlib import Path
from kit.core.graph_store import GraphStore
from kit.index.ast_indexer import V1ASTIndexer
from kit.services.cognitive_router import CognitiveRouter

def main():
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
    hotspots_parser = subparsers.add_parser("hotspots", help="Identify critical code components")
    hotspots_parser.add_argument("--limit", type=int, default=10, help="Number of hotspots to show")

    args = parser.parse_args()
    
    db_path = ".antigravity/atlas/atlas_v1.db"

    if args.command == "index":
        if args.full:
            print(f"[CLEAN] Wiping existing database for FULL index on {args.path}...")
            # Xóa file vật lý để đảm bảo sạch 100%
            for suffix in ["", "-wal", "-shm"]:
                p = Path(f"{db_path}{suffix}")
                if p.exists():
                    try:
                        p.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete {p}: {e}")
            
            # Khởi tạo mới hoàn toàn
            store = GraphStore(db_path)
            indexer = V1ASTIndexer(store)
            indexer.index_repo(args.path)
            
            # Khởi tạo registry sau full index
            from kit.index.incremental import IncrementalIndexer
            inc_indexer = IncrementalIndexer(store)
            for root, _, files in os.walk(args.path):
                for file in files:
                    if file.endswith(".py") and "venv" not in root and "test" not in root:
                        full_path = os.path.join(root, file)
                        inc_indexer.store.update_file_registry(full_path, inc_indexer.get_file_hash(full_path))
            print("[OK] Full indexing complete.")
        else:
            store = GraphStore(db_path)
            from kit.index.incremental import IncrementalIndexer
            inc_indexer = IncrementalIndexer(store)
            inc_indexer.index_incremental(args.path)
            
        # Tự động tính Importance sau mỗi lần index
        from kit.analysis.importance import GraphRankEngine
        rank_engine = GraphRankEngine(store)
        ranks = rank_engine.compute_importance()
        rank_engine.update_database(ranks)

    elif args.command == "explain":
        store = GraphStore(db_path)
        router = CognitiveRouter(store, model=None) 
        result = router.explain(args.query)
        print(f"\n🧠 .kit Explanation:\n{result}")

    elif args.command == "hotspots":
        store = GraphStore(db_path)
        from kit.analysis.importance import GraphRankEngine
        rank_engine = GraphRankEngine(store)
        hotspots = rank_engine.get_hotspots(limit=args.limit)
        
        print(f"\n🔥 Top {args.limit} Architectural Hotspots:")
        print("-" * 50)
        for fqn, kind, score in hotspots:
            print(f"  [{kind:8}] {fqn:40} | Score: {score:.4f}")

if __name__ == "__main__":
    main()
