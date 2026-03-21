import shutil
import os
from pathlib import Path

# Danh sách "tử thần"
TRASH_PATTERNS = [
    ".pytest_cache", ".mypy_cache", ".ruff_cache", 
    ".tmp_pkgtest", ".tmp_pkgtest_run", ".tmp_pkgtest_run2",
    ".tmp_pkgtest2", ".tmp_pkgtest3", "dist", "build", "__pycache__"
]

def nuclear_cleanup():
    root = Path(__file__).parent.parent
    print(f"🚀 Khởi động chiến dịch dọn dẹp tại: {root}")
    
    for pattern in TRASH_PATTERNS:
        # Sử dụng rglob để tìm tất cả các thư mục/file khớp với pattern
        for path in root.rglob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"✅ Đã tiêu diệt thư mục: {path.relative_to(root)}")
                else:
                    path.unlink(missing_ok=True)
                    print(f"✅ Đã xóa file: {path.relative_to(root)}")
            except Exception as e:
                print(f"❌ Không thể chạm vào {path.name}: {e}")

if __name__ == "__main__":
    nuclear_cleanup()
