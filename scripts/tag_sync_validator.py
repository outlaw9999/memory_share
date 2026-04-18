import re
import sys
from pathlib import Path

# SSOT: The 9 authoritative tags for v1.2.4-TITANIUM
VALID_TAGS = {
    "invariant", "decision", "preference", "note", "legacy", 
    "friction", "skill", "pattern", "hypothesis"
}

def validate_tags_in_file(file_path: Path) -> list[str]:
    """Scan file for tag="..." usage and verify against VALID_TAGS."""
    errors = []
    try:
        content = file_path.read_text(encoding="utf-8")
        # Pattern to find tag="something" or tag='something' or tag=FactTag.SOMETHING
        # We focus on string literals for now as they are the main source of drift
        matches = re.finditer(r'tag=["\']([\w-]+)["\']', content)
        for match in matches:
            tag = match.group(1)
            if tag not in VALID_TAGS:
                line_no = content.count('\n', 0, match.start()) + 1
                errors.append(f"{file_path.name}:{line_no} - Invalid tag: '{tag}'")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return errors

def main():
    repo_root = Path(__file__).resolve().parents[1]
    search_dirs = [repo_root / "kit", repo_root / "tests"]
    
    all_errors = []
    for directory in search_dirs:
        if not directory.exists():
            continue
        for py_file in directory.rglob("*.py"):
            # Skip archive
            if "archive_v123" in str(py_file):
                continue
            all_errors.extend(validate_tags_in_file(py_file))
            
    if all_errors:
        print("\u274c [TAG SYNC VIOLATION] Non-compliant tags found in v1.2.4 core:")
        for err in all_errors:
            print(f"  - {err}")
        print(f"\nTotal violations: {len(all_errors)}")
        print("Allowed tags: " + ", ".join(sorted(VALID_TAGS)))
        sys.exit(1)
    else:
        print("\u2705 [TAG SYNC OK] All tags compliant with v1.2.4-TITANIUM SSOT.")
        sys.exit(0)

if __name__ == "__main__":
    main()
