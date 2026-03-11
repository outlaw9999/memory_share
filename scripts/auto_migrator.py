import os
from pathlib import Path

# Mapping of legacy paths to new kit/ package paths
LEGACY_MAPPING = {
    "runtime": "kit",
    "brain/ops": "kit",
    "bin": "kit",
    "plugins/atlas_indexer": "kit",
    "kit_adapters.py": "kit/adapters.py",
    "kit.py": "kit/kernel.py"
}

LEGACY_DIRS = ["runtime", "brain", "reports", "bin", "plugins"]

def scan_legacy():
    print("--- .kit Auto-Migrator: Identifying Orphaned Upstream Logic ---")
    orphans = []
    
    for legacy_dir in LEGACY_DIRS:
        path = Path(legacy_dir)
        if not path.exists():
            continue
            
        for file in path.rglob("*"):
            if file.is_dir() or "__pycache__" in str(file):
                continue
            
            # Check if this file should be in kit/
            filename = file.name
            kit_path = Path("kit") / filename
            
            if not kit_path.exists():
                orphans.append((file, "NEW LOGIC - Needs manual mapping"))
            else:
                orphans.append((file, f"DUPLICATE - Possible update in {legacy_dir}"))

    if not orphans:
        print("✅ No legacy orphans found. Your kit/ structure is clean!")
        return

    print(f"Found {len(orphans)} orphaned or duplicate files from upstream merge:\n")
    for file, status in orphans:
        print(f"[{status}]")
        print(f"  Source: {file}")
        
        # Suggest destination
        suggested = "kit/" + file.name
        for legacy, target in LEGACY_MAPPING.items():
            if legacy in str(file):
                suggested = target + "/" + file.name
                break
        
        print(f"  Action: Inspect and migrate to {suggested}")
    
    print("\n--- Next Steps ---")
    print("1. View diffs: git diff origin/main HEAD -- <legacy_path>")
    print("2. Move logic to kit/")
    print("3. Delete legacy path: rm -rf <legacy_path>")

if __name__ == "__main__":
    scan_legacy()
