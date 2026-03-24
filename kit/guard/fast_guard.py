import re
from dataclasses import dataclass, field

# 🛡️ LAYER 3: REGEX OPTIMIZATION (Pre-compiled & Global)
STRING_PATTERN = re.compile(r'"[^"]*"|\'[^\']*\'')
COMMENT_PATTERN = re.compile(r"#.*|//.*")
MULTILINE_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"\s+")

# 🛡️ LAYER 1: ARTIFACT FILTER (Strict folder boundaries)
EXCLUDED_PATTERNS = [
    re.compile(r"(^|[\\/])dist([\\/]|$)"),  # Bắt cả root dist/ và nested /dist/
    re.compile(r"\.egg-info([\\/]|$)"),
    re.compile(r"\.whl$"),
    re.compile(r"\.lock$"),
    re.compile(r"\.db(-wal|-shm)?$"),  # Bắt luôn cả SQLite WAL/SHM
    re.compile(r"\.pyc$"),
]


def _empty_issues() -> list[dict[str, str]]:
    return []


def _empty_staged() -> list[str]:
    return []


@dataclass
class GuardResult:
    """Kết quả trả về từ lính gác L1"""

    passed: bool
    is_hard_block: bool = False
    issues: list[dict[str, str]] = field(default_factory=_empty_issues)
    clean_diff: str = ""
    loc_changed: int = 0
    staged_files: list[str] = field(default_factory=_empty_staged)


def is_excluded(file_path: str) -> bool:
    return any(p.search(file_path) for p in EXCLUDED_PATTERNS)


def normalize_content(code: str) -> str:
    """Heuristic to remove common comments, strings, and normalize whitespace."""
    # 🛡️ LAYER 2: SIZE CIRCUIT BREAKER (50KB limit)
    if len(code) > 50000:
        return code[:20000].lower().strip()

    code = COMMENT_PATTERN.sub("", code)
    code = MULTILINE_PATTERN.sub("", code)
    code = STRING_PATTERN.sub("", code)
    code = WHITESPACE_PATTERN.sub(" ", code)
    return code.lower().strip()


def execute_l1_guard(diff_output: str, staged_files: list[str]) -> GuardResult:
    """L1: Fast Guard Pipeline - Ultra-fast, stateless heuristic checks."""
    result = GuardResult(passed=True, staged_files=[])

    # 1. Artifact Filter
    filtered_files = [f for f in staged_files if not is_excluded(f)]
    if not filtered_files and staged_files:
        result.issues.append(
            {"type": "artifact_only", "message": "Only build artifacts staged. Skipping cognitive analysis."}
        )
        result.passed = False
        return result
    result.staged_files = filtered_files

    # 2. Binary Detection (Fail-Fast)
    if "\x00" in diff_output:
        result.issues.append({"type": "binary", "message": "[HARD] Binary content detected. Analysis aborted."})
        result.passed = False
        result.is_hard_block = True
        return result

    # 3. Size Circuit Breaker & ONLY PROCESS ADDED LINES
    if len(diff_output) > 200000:
        result.issues.append(
            {
                "type": "massive_commit",
                "message": "[WARN] Large diff (>200KB). Deep analysis truncated to protect CPU.",
            }
        )
        # Tối ưu chấn động: Chỉ quét những dòng code MỚI THÊM VÀO (+)
        added_lines = [
            line[1:] for line in diff_output.splitlines() if line.startswith("+") and not line.startswith("+++")
        ][:1000]  # Hard cap 1000 lines
        result.loc_changed = 9999
        result.clean_diff = normalize_content(" ".join(added_lines))
    else:
        added_lines = [
            line[1:] for line in diff_output.splitlines() if line.startswith("+") and not line.startswith("+++")
        ]
        result.loc_changed = len(added_lines)
        result.clean_diff = normalize_content(" ".join(added_lines))

    return result
