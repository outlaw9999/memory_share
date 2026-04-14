import logging
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger("kit.core.file_system")


class EncodingStatus(Enum):
    OK = "OK"
    BOM_DETECTED = "BOM_DETECTED"
    FALLBACK_USED = "FALLBACK_USED"
    INVALID_ENCODING = "INVALID_ENCODING"
    BINARY_FILE = "BINARY_FILE"


@dataclass
class FileContent:
    path: Path
    text: str
    encoding: str
    status: EncodingStatus
    confidence: float = 1.0


class EncodingError(Exception):
    """Raised when a file cannot be read safely due to encoding or binary content."""
    def __init__(self, path: Path, message: str, status: EncodingStatus):
        self.path = path
        self.message = message
        self.status = status
        super().__init__(f"[{status.value}] {path}: {message}")


DEFAULT_IGNORES = {
    ".git",
    ".kit",
    ".venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}

ALLOWED_EXTENSIONS = {
    ".py",
    ".rs",
    ".js",
    ".ts",
    ".go",
    ".rb",
}


def safe_walk(
    root: Path,
    *,
    max_depth: int = 25,
    follow_symlinks: bool = False,
    ignore_dirs: set[str] = DEFAULT_IGNORES,
    allowed_extensions: set[str] = ALLOWED_EXTENSIONS,
) -> Generator[Path]:
    """
    Standardized filesystem discovery layer (v1.2.4-TITANIUM).
    Protects against infinite recursion, symlink loops, and hardlink loops.
    """
    visited_inodes: set[tuple[int, int]] = set()

    def _walk(current_path: Path, depth: int) -> Generator[Path]:
        if depth > max_depth:
            logger.warning(f"Max depth reached at {current_path}")
            return

        try:
            # Use os.stat to get device and inode for loop protection
            # This handles symlinks (if followed), hardlinks, and junctions.
            stat = current_path.stat()
            inode_key = (stat.st_dev, stat.st_ino)

            if inode_key in visited_inodes:
                return

            visited_inodes.add(inode_key)

            if current_path.is_dir():
                # Directory processing
                for entry in current_path.iterdir():
                    if entry.name in ignore_dirs:
                        continue

                    # Recursively walk into everything.
                    # The inode check at the start of _walk will handle:
                    # 1. Symlink loops (if followed)
                    # 2. Hardlink deduplication (files)
                    # 3. Directory loops (junctions)

                    if entry.is_dir():
                        if entry.is_symlink() and not follow_symlinks:
                            continue
                        yield from _walk(entry, depth + 1)

                    elif entry.is_file():
                        # We also call _walk for files to ensure inode tracking
                        yield from _walk(entry, depth)

            elif current_path.is_file():
                if current_path.suffix.lower() in allowed_extensions:
                    yield current_path

        except (PermissionError, OSError) as e:
            logger.debug(f"Skipping {current_path}: {e}")
            pass

    yield from _walk(root, 0)


def read_text_safe(path: Path) -> FileContent:
    """
    Truth Acquisition Layer (v1.2.4-TITANIUM).
    Deterministic file reading pipeline: UTF-8 -> UTF-8-SIG -> UTF-16.
    Enforces a strict fail-loudly policy on binary data and encoding corruption.
    """
    try:
        raw_bytes = path.read_bytes()
    except Exception as e:
        raise EncodingError(path, f"Failed to read raw bytes: {str(e)}", EncodingStatus.INVALID_ENCODING) from e

    if not raw_bytes:
        return FileContent(path, "", "utf-8", EncodingStatus.OK)

    # 1. Check for UTF-8-SIG or UTF-16 BOM first.
    # This protects UTF-16 files (which often contain NULL bytes) from being flagged as binary.
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        try:
            text = raw_bytes.decode('utf-8-sig')
            return FileContent(path, text, 'utf-8-sig', EncodingStatus.BOM_DETECTED)
        except Exception:
            pass

    if raw_bytes.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            # Note: utf-16 decoder handles the BOM automatically
            text = raw_bytes.decode('utf-16')
            return FileContent(path, text, 'utf-16', EncodingStatus.BOM_DETECTED)
        except Exception:
            pass

    # 2. Binary Check (only if no BOM is present)
    # Heuristic: If NULL byte is present and not part of a known encoding, it's likely binary.
    if b'\x00' in raw_bytes:
        raise EncodingError(path, "NULL byte detected in non-BOM file. Likely binary content.", EncodingStatus.BINARY_FILE)

    # 3. Deterministic Pipeline: UTF-8 -> Fail
    try:
        text = raw_bytes.decode('utf-8')
        return FileContent(path, text, 'utf-8', EncodingStatus.OK)
    except UnicodeDecodeError as e:
        # If UTF-8 fails and we reached here (no NULL bytes), it's either high-bit ANSI or Corrupted.
        # Kit V1.2.4 policy: We DO NOT guess. We FAIL.
        raise EncodingError(
            path,
            "UTF-8 decoding failed and no valid fallback was found. Kit avoids silent corruption.",
            EncodingStatus.INVALID_ENCODING,
        ) from e
