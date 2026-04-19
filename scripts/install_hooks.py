#!/usr/bin/env python3
"""
Install Git hooks for Kit + Vantage integration.

Usage:
    python scripts/install_hooks.py
    python scripts/install_hooks.py --uninstall
"""

import argparse
import os
import sys
from pathlib import Path
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def get_hooks_dir() -> Path:
    """Find .git/hooks directory."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        git_dir = parent / ".git"
        if git_dir.is_dir():
            return git_dir / "hooks"
    raise RuntimeError("Not in a git repository")


def install_hook(platform: str = "auto") -> bool:
    """Install pre-commit hook."""
    hooks_dir = get_hooks_dir()

    if platform == "auto":
        platform = "powershell" if sys.platform == "win32" else "sh"

    hook_file = "pre-commit-kit"
    source = Path(__file__).parent / "hooks" / hook_file

    if not source.exists():
        print(f"Error: Source hook not found: {source}")
        return False

    target = hooks_dir / "pre-commit"

    try:
        content = source.read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8")

        if platform == "sh":
            os.chmod(target, 0o755)

        print(f"✅ Installed: {target}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def uninstall_hook() -> bool:
    """Remove pre-commit hook."""
    hooks_dir = get_hooks_dir()
    target = hooks_dir / "pre-commit"

    if not target.exists():
        print("No hook installed")
        return True

    try:
        target.unlink()
        print(f"✅ Removed: {target}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Install Git hooks for Kit")
    parser.add_argument("--uninstall", action="store_true", help="Remove installed hook")
    parser.add_argument("--platform", choices=["auto", "sh", "powershell"], default="auto")
    args = parser.parse_args()

    if args.uninstall:
        success = uninstall_hook()
    else:
        success = install_hook(args.platform)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()