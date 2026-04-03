import shutil
import os
from pathlib import Path

# Target list for deletion
TRASH_PATTERNS = [
    ".pytest_cache", ".mypy_cache", ".ruff_cache", 
    ".tmp_pkgtest", ".tmp_pkgtest_run", ".tmp_pkgtest_run2",
    ".tmp_pkgtest2", ".tmp_pkgtest3", "dist", "build", "__pycache__"
]

def nuclear_cleanup():
    root = Path(__file__).parent.parent
    print(f"[CLEANUP] Starting nuclear purge at: {root}")
    
    for pattern in TRASH_PATTERNS:
        # Sử dụng rglob để tìm tất cả các thư mục/file khớp với pattern
        for path in root.rglob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"[PURGED] Deleted directory: {path.relative_to(root)}")
                else:
                    path.unlink(missing_ok=True)
                    print(f"[PURGED] Deleted file: {path.relative_to(root)}")
            except Exception as e:
                print(f"[REJECTED] Cannot touch {path.name}: {e}")

if __name__ == "__main__":
    nuclear_cleanup()
