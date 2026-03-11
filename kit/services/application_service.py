import os
import json
from pathlib import Path
from typing import Dict, Any

from ..core import GraphStore, AtlasIndexer, Scanner

class ApplicationService:
    """Application layer service for standard kit operations."""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root or os.environ.get("ANTIGRAVITY_WORKSPACE_ROOT", os.getcwd()))
        self.db_path = self.workspace_root / ".antigravity" / "atlas" / "atlas.db"
        self.queries_dir = self.workspace_root / ".antigravity" / "queries"
        
    def init_infrastructure(self) -> str:
        atlas_dir = self.workspace_root / ".antigravity" / "atlas"
        atlas_dir.mkdir(parents=True, exist_ok=True)
        self.queries_dir.mkdir(parents=True, exist_ok=True)
        
        gitignore = self.workspace_root / ".gitignore"
        line_to_add = ".antigravity/\n"
        if gitignore.exists():
            content = gitignore.read_text()
            if ".antigravity/" not in content:
                with open(gitignore, "a") as f:
                    f.write("\n# Antigravity Data\n" + line_to_add)
        else:
            gitignore.write_text("# Antigravity Data\n" + line_to_add)
        return f"Initialized .kit infrastructure at {self.workspace_root}/.antigravity/"

    def index_codebase(self) -> str:
        """
        Scans and indexes the codebase.
        Uses os.walk with directory pruning for maximum performance.
        """
        import time
        import os
        start_time = time.time()
        
        # Black-hole directories to ignore
        IGNORE_DIRS = {
            '.git', '.venv', 'venv', 'env', 'node_modules', 
            '__pycache__', 'dist', 'build', '.antigravity'
        }
        
        store = GraphStore(self.db_path)
        conn = store.conn
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=OFF;")
        
        scanner = Scanner()
        processed_count = 0
        
        try:
            for root, dirs, files in os.walk(self.workspace_root):
                # Prune ignore directories in-place
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
                
                for file in files:
                    if file.endswith(".py"):
                        py_file = Path(root) / file
                        symbols = scanner.scan_file(py_file)
                        calls = scanner.scan_calls(py_file)
                        store.update_file(py_file, symbols, calls)
                        processed_count += 1
            
            conn.commit()
            conn.execute("VACUUM;")
        except Exception as e:
            conn.rollback()
            raise Exception(f"Index failed: {e}")

        return f"Indexed {processed_count} files in {time.time() - start_time:.2f}s."

    def run_sql_stone(self, query_name: str, params=None, timeout=30) -> Any:
        import sqlite3
        query_file = self.queries_dir / "stones" / f"{query_name}.sql"
        if not query_file.exists():
            query_file = self.queries_dir / f"{query_name}.sql"
        
        if not query_file.exists():
            raise FileNotFoundError(f"Query Stone '{query_name}' not found.")
        
        query_text = query_file.read_text()
        try:
            conn = sqlite3.connect(self.db_path, timeout=float(timeout))
            conn.row_factory = sqlite3.Row
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
            raise Exception(f"Error executing SQL Stone '{query_name}': {e}")
