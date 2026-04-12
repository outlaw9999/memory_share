import re
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum

from kit.core.kit_cognitive_core import SAMBrain
from kit.guard.fast_guard import execute_l1_guard


class ConflictLevel(StrEnum):
    HARD = "hard"
    SOFT = "soft"


# 🛡️ GLOBAL TECH PATTERNS (L3: Cognitive Signatures)
TECH_PATTERNS = {
    "redis": [re.compile(r"\bimport redis\b"), re.compile(r"\bfrom redis\b")],
    "postgres": [re.compile(r"\bpsycopg\b"), re.compile(r"\bpostgres\b"), re.compile(r"\bpostgresql\b")],
    "sqlite": [re.compile(r"\bsqlite3?\b")],
    "fastapi": [re.compile(r"\bfastapi\b"), re.compile(r"\bstarlette\b")],
    "flask": [re.compile(r"\bflask\b"), re.compile(r"\bwerkzeug\b")],
}


@dataclass
class PreflightResult:
    status: str = "pass"
    score: float = 1.0
    issues: list[dict[str, str]] = field(default_factory=lambda: [])
    suggestions: list[str] = field(default_factory=lambda: [])


def run_preflight(
    commit_msg: str,
    brain: SAMBrain,
    strict_mode: bool = False,
    limit: int = 20,
    diff_text: str | None = None,
) -> PreflightResult:
    result = PreflightResult()

    # --- LAYER 0: Fetch Input ---
    if diff_text is None:
        try:
            diff_output = subprocess.check_output(
                ["git", "diff", "--cached", "--unified=0"],
                stderr=subprocess.DEVNULL,
                text=True,
                errors="replace",
                timeout=3.0,
            )
            staged_files = subprocess.check_output(
                ["git", "diff", "--cached", "--name-only"],
                stderr=subprocess.DEVNULL,
                text=True,
                errors="replace",
                timeout=3.0,
            ).splitlines()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            result.issues.append({"type": "git", "message": "Not a git repository or no staged files."})
            result.status = "block"
            result.score = 0.0
            return result
    else:
        diff_output = diff_text
        staged_files = ["<stdin>"]

    # --- LAYER 1: Fast Guard (Sacrificial Layer) ---
    guard_res = execute_l1_guard(diff_output, staged_files)

    # Carry over any issues/warnings from L1 (Massive commit, etc.)
    result.issues.extend(guard_res.issues)

    if not guard_res.passed:
        if guard_res.is_hard_block:
            # Hard violation (e.g. Binary Data detected) -> BLOCK immediately
            result.status = "block"
            result.score = 0.0
            return result
        else:
            # Soft failure (e.g. Artifact Only). No actual code for L3 to analyze.
            # Safely bypass L3 and allow the commit.
            result.status = "pass"
            return result

    # If L1 passes (Valid text, possibly truncated) -> Proceed to L3
    clean_diff = guard_res.clean_diff
    loc_changed = guard_res.loc_changed
    staged_files = guard_res.staged_files

    # --- LAYER 2: Structural Analysis (Placeholder for L2 Sensors like Vantage) ---
    # Shadow Signal Collection (Phase 0: Regex Sensors)
    from kit.core.shadow import run_shadow_scan

    for f in staged_files:
        if f != "<stdin>":
            run_shadow_scan(f, brain.root_path)

    # --- LAYER 3: Cognitive Governance ---

    # Step 3.1: Semantics Rule Check (Commit Message)
    # [AMSB v1.2.3] Bypass message checks if diff is provided (Git Hook mode)
    if commit_msg:
        if len(commit_msg) < 10:
            result.score -= 0.3
            result.issues.append({"type": "commit_message", "message": "Message too short (< 10 chars)."})

        generic_words = ["update", "fix", "stuff", "changes", "wip"]
        if any(word in commit_msg.lower() for word in generic_words) and len(commit_msg) < 15:
            result.score -= 0.3
            result.issues.append({"type": "commit_message", "message": "Message is too generic."})
            result.suggestions.append("Format hint: feat(scope): specific description")

        match = re.search(r"^(feat|fix|docs|style|refactor|perf|test|chore)(\(.+\))?:.+$", commit_msg)
        if not match:
            result.score -= 0.2
            result.issues.append({"type": "commit_message", "message": "Does not follow Conventional Commits format."})
            result.suggestions.append("Example: feat(auth): add JWT validation")
    elif diff_text is None:
        # Fallback for empty message when no diff is present
        result.score -= 0.5
        result.issues.append({"type": "commit_message", "message": "No commit message provided."})

    # Step 3.2: Cognitive Alignment Check (Retrieve Facts from Brain)
    sem_rows = brain.get_semantic_observations(limit=min(limit, 15))

    # 🛡️ CPU LOOP GUARD
    max_checks = 50
    checks_done = 0

    for row in sem_rows:
        if result.status == "block" or checks_done >= max_checks:
            break

        fact_tag = row["tag"]
        fact_content = row["content"].lower()

        forbidden_tech = []
        if "sqlite" in fact_content and any(w in fact_content for w in ["only", "must", "always"]):
            forbidden_tech = ["redis", "postgres"]
        elif "postgres" in fact_content and any(w in fact_content for w in ["only", "must", "always"]):
            forbidden_tech = ["redis", "sqlite"]

        for tech in forbidden_tech:
            for pattern in TECH_PATTERNS.get(tech, []):
                checks_done += 1
                if checks_done > max_checks:
                    break
                if pattern.search(clean_diff):
                    is_hard = fact_tag == "invariant"
                    penalty = 0.5 if is_hard else 0.2
                    level = ConflictLevel.HARD if is_hard else ConflictLevel.SOFT

                    result.score -= penalty
                    result.issues.append(
                        {
                            "type": "alignment",
                            "message": f"[{level.upper()}] Diff introduces '{tech}' which violates '{fact_content[:40]}...'",
                        }
                    )
                    if is_hard:
                        result.status = "block"
                        break
            if result.status == "block" or checks_done > max_checks:
                break

    # 3. L3: Documentation Sync Check
    docs_changed = any("AGENTS.md" in f or "README.md" in f for f in staged_files)
    if diff_text is None and loc_changed > 30 and not docs_changed:
        result.score -= 0.2
        result.issues.append(
            {
                "type": "doc_drift",
                "message": f"Significant code changes ({loc_changed} LOC) without updating AGENTS.md or documentation.",
            }
        )
        result.suggestions.append("Consider updating AGENTS.md to reflect these architectural changes.")

    # 4. L4: Version Sync Check
    from pathlib import Path

    arch_file = Path("ARCHITECTURE.md")
    if arch_file.exists():
        try:
            with open(arch_file, encoding="utf-8") as f:
                arch_content = f.read()
            if "Version: v1.2.3" not in arch_content:
                result.score -= 0.5
                result.issues.append(
                    {
                        "type": "version_drift",
                        "message": "[HARD] ARCHITECTURE.md version mismatch. Expected v1.2.3.",
                    }
                )
                result.status = "block"
        except Exception:
            pass

    # 5. L5: Noise Control
    if loc_changed <= 2 and "fix" not in commit_msg.lower():
        result.score -= 0.1
        result.issues.append(
            {
                "type": "noise",
                "message": "Commit is very small. Consider squashing if it's part of a larger logical change.",
            }
        )

    # Apply bounds and classify
    result.score = max(0.0, min(1.0, result.score))

    if result.score >= 0.8:
        result.status = "pass"
    elif 0.5 <= result.score < 0.8:
        result.status = "warn"
    else:
        result.status = "block"

    if strict_mode and result.status == "warn":
        result.status = "block"

    return result
