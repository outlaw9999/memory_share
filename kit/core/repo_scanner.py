import os
from pathlib import Path
from typing import Any

from kit.core.deterministic import deterministic_json, stable_hash

SCHEMA_VERSION = "1.0"

# Highly restricted fallback list
IGNORE_DIRS = {
    ".git",
    ".kit",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
    "env",
    "build",
    "dist",
}

IGNORE_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".class",
    ".o",
}


def load_ignore_patterns(root_path: Path) -> tuple[set[str], set[str]]:
    """Load ignores from .kitignore and .gitignore, falling back to defaults."""
    dirs = set(IGNORE_DIRS)
    exts = set(IGNORE_EXTS)

    # 1. Load .gitignore (Minimalist - skip complex globs to avoid hash drift)
    gitignore = root_path / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "!" in line or "**" in line:
                # Silently skip complex patterns as requested
                continue

            # Simple heuristic mapping
            if line.endswith("/"):
                dirs.add(line[:-1])
            elif line.startswith("*."):
                exts.add(line[1:])
            elif "/" not in line:
                dirs.add(line)

    # 2. Load .kitignore (Specific overrides for cognitive scanner)
    kitignore = root_path / ".kitignore"
    if kitignore.exists():
        lines = kitignore.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("*."):
                exts.add(line[1:])  # extract .extension
            elif line.endswith("/"):
                dirs.add(line[:-1])
            else:
                dirs.add(line)

    return dirs, exts


def scan_repo(root_path: Path) -> dict[str, Any]:
    """
    Physical awareness scan.
    Output: Deterministic repo_map with files and modules.
    No semantic parsing. No AST reading. Zero file reading.
    """
    files: list[str] = []

    ignore_dirs, ignore_exts = load_ignore_patterns(root_path)

    # 1. Gather all files deterministically
    for parent, dirs_list, filenames in os.walk(root_path):
        # Prune ignored directories immediately
        dirs_list[:] = [d for d in dirs_list if d not in ignore_dirs]

        parent_path = Path(parent)
        for name in filenames:
            ext = os.path.splitext(name)[1]
            if ext in ignore_exts or name in {".DS_Store"}:
                continue

            p = parent_path / name
            try:
                rel = p.relative_to(root_path)
                # Store paths generically with forward slashes for cross-OS stability
                files.append(str(rel).replace("\\", "/"))
            except ValueError:
                pass

    files.sort()

    # 2. Extract modules names using very minimal heuristics
    modules: set[str] = set()
    for f in files:
        if f.endswith(".py"):
            parts = f.split("/")
            if parts[-1] == "__init__.py":
                mod = ".".join(parts[:-1])
            else:
                mod = ".".join(parts)[:-3]
            if mod:
                modules.add(mod)
        elif f.endswith(".rs") or f.endswith(".js") or f.endswith(".ts") or f.endswith(".go"):
            # Simple heuristic for other languages
            mod = f.rsplit(".", 1)[0].replace("/", ".")
            if mod:
                modules.add(mod)

    modules_sorted = sorted(list(modules))

    repo_map = {
        "schema_version": SCHEMA_VERSION,
        "repo_hash": "",  # placeholder
        "files": files,
        "modules": modules_sorted,
    }

    # 3. Hash the dictionary without the temporary empty hash
    # To create a fully stable hash, we compute signature of the content.
    del repo_map["repo_hash"]
    sig = deterministic_json(repo_map)

    # Put hash back
    repo_map["repo_hash"] = stable_hash(sig)

    # Ensure ordered dict output
    final_repo_map = {
        "schema_version": repo_map["schema_version"],
        "repo_hash": repo_map["repo_hash"],
        "files": repo_map["files"],
        "modules": repo_map["modules"],
    }

    return final_repo_map


def save_repo_map(root_path: Path) -> Path:
    """Scan and save the official repo_map artifact to .kit/repo_map.json."""
    repo_map_content = scan_repo(root_path)

    kit_dir = root_path / ".kit"
    kit_dir.mkdir(parents=True, exist_ok=True)

    out_path = kit_dir / "repo_map.json"

    json_str = deterministic_json(repo_map_content)
    # Using utf-8 because deterministic_json has ensure_ascii=False
    out_path.write_text(json_str, encoding="utf-8")
    return out_path
