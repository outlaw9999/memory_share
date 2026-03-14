import os
from pathlib import Path
from typing import Iterator

# Thư mục "cấm địa" khiến hệ thống bị treo
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "venv",
    "__pycache__",
    ".antigravity",
    "dist",
    "build",
}
MAX_DEPTH = 10  # Giới hạn độ sâu để tránh vòng lặp vô hạn


def safe_walk(root_path: str | Path) -> Iterator[Path]:
    """Quét file an toàn, không follow symlink, không vào vùng cấm."""
    root = Path(root_path)
    for dirpath, dirnames, filenames in os.walk(root):
        # 1. Cắt tỉa các thư mục bị cấm ngay tại chỗ
        dirnames[:] = sorted([d for d in dirnames if d not in IGNORED_DIRS])

        # 2. Kiểm tra độ sâu
        try:
            depth = len(Path(dirpath).relative_to(root).parts)
        except ValueError:
            # handle cases where dirpath is not relative to root
            continue

        if depth > MAX_DEPTH:
            dirnames[:] = []  # Dừng quét sâu hơn
            continue

        for f in sorted(filenames):
            yield Path(dirpath) / f
