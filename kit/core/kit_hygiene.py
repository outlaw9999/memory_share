import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from kit.core.command_registry import CommandNamespace, CommandSideEffect, kit_command

logger = logging.getLogger("kit.hygiene")


class FileCategory(StrEnum):
    KERNEL = "kernel"
    CODE = "code"
    GOVERNANCE = "governance"
    ARTIFACT = "artifact"
    TEMP = "temp"
    NOISE = "noise"
    UNKNOWN = "unknown"


@dataclass
class HygieneReport:
    total_files: int = 0
    categories: dict[FileCategory, list[str]] = field(default_factory=lambda: {c: [] for c in FileCategory})
    noise_score: float = 0.0  # 0.0 (Clean) to 1.0 (Entropy Hell)
    suggestions: list[str] = field(default_factory=list)


def classify_file(path: Path, root_path: Path) -> FileCategory:
    """Classifies a file based on its path and naming convention (v1.2.5)."""
    rel_path = path.relative_to(root_path)
    parts = rel_path.parts
    name = path.name

    if ".kit" in parts:
        if name.endswith(".db") or name.endswith(".json"):
            return FileCategory.KERNEL
        return FileCategory.ARTIFACT

    if "kit" in parts:
        return FileCategory.CODE

    if name in (
        "AGENTS.md",
        "implementation_plan.md",
        "walkthrough.md",
        "task.md",
        "README.md",
        "LICENSE",
        "MIGRATION.md",
        "pyproject.toml",
        ".gitignore",
        "kit-test-gate.yaml",
    ):
        return FileCategory.GOVERNANCE

    if name.startswith("debug_") or "tmp" in name.lower() or name.endswith(".log"):
        return FileCategory.TEMP

    if name.endswith((".pyc", ".pyo", ".DS_Store")):
        return FileCategory.NOISE

    if path.suffix in (".py", ".rs", ".js", ".ts", ".go", ".c", ".cpp", ".ps1"):
        return FileCategory.CODE

    if path.suffix in (".yaml", ".yml", ".json", ".md"):
        return FileCategory.ARTIFACT

    return FileCategory.UNKNOWN


def generate_hygiene_report(root_path: Path) -> HygieneReport:
    """Scans the workspace and generates a hygiene assessment."""
    report = HygieneReport()

    # Simple recursive scan excluding typical ignores
    ignore_dirs = {".git", ".venv", "node_modules", "__pycache__", ".gemini"}

    for p in root_path.rglob("*"):
        if p.is_dir():
            if p.name in ignore_dirs:
                continue
            continue

        # Check if parent is ignored
        if any(ignored in p.parts for ignored in ignore_dirs):
            continue

        report.total_files += 1
        category = classify_file(p, root_path)
        report.categories[category].append(str(p.relative_to(root_path)))

    # Calculate Noise Score
    temp_count = len(report.categories[FileCategory.TEMP])
    noise_count = len(report.categories[FileCategory.NOISE])
    unknown_count = len(report.categories[FileCategory.UNKNOWN])

    if report.total_files > 0:
        report.noise_score = (temp_count + noise_count + (unknown_count * 0.5)) / report.total_files

    if report.noise_score > 0.1:
        report.suggestions.append(f"Noise level high ({report.noise_score:.2f}). Run 'kit doctor --heal' to cleanup.")

    if len(report.categories[FileCategory.TEMP]) > 5:
        report.suggestions.append("Excessive temp/debug files detected. Archive required.")

    # v1.2.5-TITANIUM: Check for Scope Bleed (Stray local brains in global home)
    from kit.core.memory_topology import MemoryTopology

    global_kit = MemoryTopology().GLOBAL_KIT_HOME
    stray_local = global_kit / "local_brain.db"
    if stray_local.exists():
        report.suggestions.append(
            f"SCOPE BLEED DETECTED: Stray local brain at {stray_local}. Run 'kit doctor --heal' to merge and purge."
        )

    # v1.2.5-TITANIUM: System Temp Pressure
    import tempfile

    temp_dir = Path(tempfile.gettempdir())
    kit_temp_count = len(list(temp_dir.glob("kit_*")))
    if kit_temp_count > 3:
        report.suggestions.append(
            f"System temp pressure high ({kit_temp_count} files). Run 'kit doctor --heal' to enforce 3-file limit."
        )

    return report


def perform_hygiene_cleanup(root_path: Path, dry_run: bool = True) -> list[str]:
    """Executes the cleanup DAG (v1.2.5-TITANIUM). Returns list of removed files."""
    report = generate_hygiene_report(root_path)
    removed = []

    # DAG Order: TEMP -> NOISE
    # Removing ephemeral execution state before build artifacts
    for category in [FileCategory.TEMP, FileCategory.NOISE]:
        for rel_path in report.categories[category]:
            p = root_path / rel_path
            if p.exists():
                if not dry_run:
                    try:
                        p.unlink()
                        removed.append(rel_path)
                        logger.info(f"Cleanup: Removed {rel_path} ({category})")
                    except OSError as e:
                        logger.error(f"Failed to remove {rel_path}: {e}")
                else:
                    removed.append(rel_path)

    # 3. System Temp Hygiene (v1.2.5-TITANIUM Restriction: Max 3 files)
    removed_temp = perform_system_temp_cleanup(dry_run=dry_run)
    removed.extend(removed_temp)

    return removed


def perform_system_temp_cleanup(dry_run: bool = True) -> list[str]:
    """
    Scans the system temp directory for Kit-prefixed artifacts.
    Enforces a strict limit of 3 files (FIFO).
    """
    import tempfile

    temp_dir = Path(tempfile.gettempdir())
    # Find files starting with kit_
    kit_files = sorted(list(temp_dir.glob("kit_*")), key=lambda p: p.stat().st_mtime)

    removed = []
    # If we have more than 3, remove the oldest ones until we have only 2 left (to be safe)
    # Actually user said "không được quá 3", so 3 is the limit.
    if len(kit_files) > 3:
        to_delete = kit_files[:-3]  # Keep the 3 newest
        for p in to_delete:
            if not dry_run:
                try:
                    p.unlink()
                    removed.append(f"TEMP:{p.name}")
                    logger.info(f"System Temp Cleanup: Removed {p.name}")
                except OSError as e:
                    logger.error(f"Failed to remove system temp {p.name}: {e}")
            else:
                removed.append(f"TEMP:{p.name}")

    return removed


@kit_command(
    name="hygiene",
    namespace=CommandNamespace.DIAGNOSTIC,
    description="Workspace Governance: Audit codebase hygiene and artifact entropy",
    side_effect=CommandSideEffect.READ_ONLY,
)
def handle_hygiene(args, print_diagnostic, **kwargs):
    """CLI handler for kit hygiene."""
    from pathlib import Path

    root_path = Path.cwd()
    report = generate_hygiene_report(root_path)

    print_diagnostic("Workspace Hygiene Report (v1.2.5-TITANIUM)")
    print_diagnostic(f"Total Files tracked: {report.total_files}")
    print_diagnostic(
        f"Entropy Score: {report.noise_score:.2f} ({'STABLE' if report.noise_score < 0.1 else 'DRIFTING'})"
    )

    print_diagnostic("\nBreakdown:")
    for cat, files in report.categories.items():
        if files:
            print_diagnostic(f"  {cat.upper():<10}: {len(files)} files")

    if report.suggestions:
        print_diagnostic("\nGovernance Suggestions:")
        for sug in report.suggestions:
            print_diagnostic(f"  - {sug}")

    if getattr(args, "verbose", False):
        if report.categories[FileCategory.TEMP]:
            print_diagnostic("\nDisposable Artifacts:")
            for f in report.categories[FileCategory.TEMP]:
                print_diagnostic(f"  [TEMP] {f}")

        if report.categories[FileCategory.UNKNOWN]:
            print_diagnostic("\nUnclassified Files (Noise):")
            for f in report.categories[FileCategory.UNKNOWN]:
                print_diagnostic(f"  [?] {f}")
