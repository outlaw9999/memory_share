import hashlib
import os
import subprocess
from pathlib import Path
from typing import List, Set
from kit.core.graph_store import GraphStore
from kit.index.ast_indexer import V1ASTIndexer

class IncrementalIndexer:
    def __init__(self, store: GraphStore):
        self.store = store
        self.indexer = V1ASTIndexer(store)

    def get_file_hash(self, file_path: str) -> str:
        """Tính MD5 hash của file."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def get_changed_files_git(self, root_path: str) -> Set[str]:
        """Lấy danh sách file thay đổi từ Git (staged + unstaged)."""
        try:
            # Lấy tất cả file thay đổi so với HEAD
            output = subprocess.check_output(
                ["git", "diff", "HEAD", "--name-only"], 
                cwd=root_path, 
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            # Thêm cả untracked files
            output += subprocess.check_output(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=root_path,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            files = set()
            for line in output.splitlines():
                if line.endswith(".py"):
                    files.add(os.path.join(root_path, line))
            return files
        except Exception:
            return set()

    def index_incremental(self, root_path: str):
        """Thực hiện index gia tăng."""
        print(f"[*] Starting Incremental Index on {root_path}...")
        
        # 1. Thử dùng Git để tối ưu hóa phạm vi quét (candidate files)
        git_changed = self.get_changed_files_git(root_path)
        
        # 2. Quét toàn bộ repo để so sánh Hash (đảm bảo tính nhất quán nếu Git không chuẩn)
        to_index = []
        for root, _, files in os.walk(root_path):
            for file in files:
                if not file.endswith(".py"): continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_path)
                
                # Bỏ qua venv/test
                if "venv" in full_path or "test" in full_path: continue
                
                current_hash = self.get_file_hash(full_path)
                registered_hash = self.store.get_registered_hash(full_path)
                
                if current_hash != registered_hash:
                    to_index.append((full_path, rel_path, current_hash))
                    
        if not to_index:
            print("[v] No changes detected. Graph is up to date.")
            return

        print(f"[^] Found {len(to_index)} changed files. Updating graph...")
        
        for full_path, rel_path, f_hash in to_index:
            module_name = rel_path.replace(os.path.sep, ".").removesuffix(".py")
            
            # Ghost Nodes Cleanup
            print(f"  [-] Cleaning stale data for {module_name}...")
            self.store.delete_file_metadata(full_path)
            
            # Re-index
            print(f"  [+] Re-indexing {module_name}...")
            self.indexer.index_file(full_path, module_name)
            
            # Update Registry
            self.store.update_file_registry(full_path, f_hash)
            
        print("[OK] Incremental indexing complete.")
