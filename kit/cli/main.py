import argparse
import sqlite3
from kit.core.graph_store import GraphStore
from kit.index.ast_indexer import V1ASTIndexer
from kit.services.cognitive_router import CognitiveRouter

def main():
    parser = argparse.ArgumentParser(description=".kit V1: Agent Knowledge Kernel")
    subparsers = parser.add_subparsers(dest="command")

    # Command: index
    index_parser = subparsers.add_parser("index", help="Index codebase into Graph")
    index_parser.add_argument("path", default=".", help="Path to codebase")

    # Command: explain
    explain_parser = subparsers.add_parser("explain", help="Explain code logic")
    explain_parser.add_argument("query", help="Natural language query")

    args = parser.parse_args()
    
    # Store initialization triggers schema creation
    db_path = ".antigravity/atlas/atlas.db"
    store = GraphStore(db_path)

    if args.command == "index":
        print(f"🔍 Indexing {args.path} into Canonical Alias Graph...")
        
        # Reset tables for clean index
        store.conn.execute("DELETE FROM symbols")
        store.conn.execute("DELETE FROM edges")
        store.conn.execute("DELETE FROM symbol_aliases")
        # Thay vì DELETE FROM symbol_fts, ta DROP và RECREATE
        store.conn.execute("DROP TABLE IF EXISTS symbol_fts")
        store._recreate_symbol_search(store.conn.cursor())
        store.conn.commit()
        
        indexer = V1ASTIndexer(store)
        indexer.index_repo(args.path)
        print("✅ Indexing complete.")

    elif args.command == "explain":
        router = CognitiveRouter(store, model=None) 
        result = router.explain(args.query)
        print(f"\n🧠 .kit Explanation:\n{result}")

if __name__ == "__main__":
    main()
