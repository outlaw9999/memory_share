#!/usr/bin/env python3
"""
Bulk Migration Script for Test Suite v1.2.4

Migrates legacy kit_agent imports to kit imports in test files.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

def migrate_file(file_path):
    """Migrate a single test file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace kit_agent imports with kit
    original = content
    content = re.sub(r'from kit_agent\.', 'from kit.', content)
    content = re.sub(r'import kit_agent\.', 'import kit.', content)

    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Migrated: {file_path}")
        return True
    return False

def main():
    migrated_count = 0
    for root, dirs, files in os.walk(TESTS_DIR):
        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                file_path = Path(root) / file
                if migrate_file(file_path):
                    migrated_count += 1

    print(f"Migration complete. Updated {migrated_count} files.")

if __name__ == "__main__":
    main()