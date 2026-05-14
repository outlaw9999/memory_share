"""FS executor for dispatcher."""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("kit.fs_dispatch")


def run_fs(command: str, args) -> int:
    """Direct filesystem execution without reasoning."""
    if command == "where":
        cwd = Path.cwd()
        print(f"CWD:   {cwd}")
        print(f"Local: {cwd / '.kit' / 'local_brain.db'}")
        return 0

    elif command == "list":
        raw_path = getattr(args, "path", None)
        if raw_path is None and len(sys.argv) > 2:
            raw_path = sys.argv[2]
        path = raw_path or "."
        try:
            entries = os.listdir(path)
            for e in sorted(entries):
                print(e)
            return 0
        except Exception as e:
            logger.error(f"List failed: {e}")
            return 1

    logger.error("Unsupported filesystem command: %s", command)
    return 1
