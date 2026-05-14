#!/usr/bin/env python3
"""
Install Git hooks for Kit v1.2.5 — Runtime Integration.

Installs pre-commit, post-commit, and post-merge hooks.
Each hook calls `kit-runtime runtime --hook <event>` to emit intents.

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

HOOK_NAMES = ("pre-commit", "post-commit", "post-merge")


def get_hooks_dir() -> Path:
    """Find .git/hooks directory."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        git_dir = parent / ".git"
        if git_dir.is_dir():
            return git_dir / "hooks"
    raise RuntimeError("Not in a git repository")


def install_all(platform: str = "auto") -> bool:
    """Install all 3 git hooks."""
    hooks_dir = get_hooks_dir()

    if platform == "auto":
        platform = "powershell" if sys.platform == "win32" else "sh"

    all_ok = True
    for hook_name in HOOK_NAMES:
        source_file = f"{hook_name}-kit"
        if platform == "powershell":
            source_file += ".ps1"
        source = Path(__file__).parent / "hooks" / source_file

        if not source.exists():
            print(f"⚠️  Source hook not found: {source}")
            all_ok = False
            continue

        target = hooks_dir / hook_name
        try:
            content = source.read_text(encoding="utf-8")
            target.write_text(content, encoding="utf-8")
            if platform != "powershell":
                os.chmod(target, 0o755)
            print(f"✅ Installed: {target}")
        except Exception as e:
            print(f"❌ Error installing {hook_name}: {e}")
            all_ok = False

    return all_ok


def uninstall_all() -> bool:
    """Remove all 3 git hooks."""
    hooks_dir = get_hooks_dir()
    all_ok = True

    for hook_name in HOOK_NAMES:
        target = hooks_dir / hook_name
        if not target.exists():
            print(f"ℹ️  No hook: {target}")
            continue
        try:
            target.unlink()
            print(f"✅ Removed: {target}")
        except Exception as e:
            print(f"❌ Error removing {hook_name}: {e}")
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Install Git hooks for Kit v1.2.5")
    parser.add_argument("--uninstall", action="store_true", help="Remove installed hooks")
    parser.add_argument("--platform", choices=["auto", "sh", "powershell"], default="auto")
    args = parser.parse_args()

    if args.uninstall:
        success = uninstall_all()
    else:
        success = install_all(args.platform)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
