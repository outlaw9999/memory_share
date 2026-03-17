import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum
from kit.core.kit_cognitive_core import SAMBrain
from pathlib import Path

class ConflictLevel(str, Enum):
    SOFT = "soft"
    HARD = "hard"

@dataclass
class PreflightResult:
    status: str = "pass"
    score: float = 1.0
    issues: List[Dict[str, str]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

def normalize_content(code: str) -> str:
    """Heuristic to remove common comments, strings, and normalize whitespace from code diffs."""
    # Remove single line comments (Python, JS, Shell)
    code = re.sub(r'#.*|//.*', '', code)
    # Remove multi-line comments (JS/C-style)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Remove strings
    code = re.sub(r'".*?"|\'.*?\'', '', code)
    # Normalize whitespace
    code = re.sub(r'\s+', ' ', code)
    return code.lower().strip()

def run_preflight(commit_msg: str, brain: SAMBrain, strict_mode: bool = False, limit: int = 20) -> PreflightResult:
    result = PreflightResult()
    
    # 1. Fetch Staged Changes
    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--cached", "--unified=0"], 
            stderr=subprocess.STDOUT, text=True, errors='replace'
        )
        staged_files = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], 
            text=True, errors='replace'
        ).splitlines()
    except subprocess.CalledProcessError:
        result.issues.append({"type": "git", "message": "Not a git repository or no staged files."})
        result.status = "block"
        result.score = 0.0
        return result

    if not staged_files:
        result.issues.append({"type": "empty", "message": "No files staged for commit."})
        result.status = "block"
        result.score = 0.0
        return result

    # Calculate LOC roughly
    loc_changed = len([line for line in diff_output.splitlines() if line.startswith('+') and not line.startswith('+++')])

    # 2. L1: Semantics Rule Check
    if not commit_msg or len(commit_msg) < 10:
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

    # 3. L2: Cognitive Alignment Check
    # We fetch top invariant/decision facts to see if diff violates them.
    conn = brain._get_connection()
    try:
        sem_rows = conn.execute("""
            SELECT tag, content FROM observations 
            WHERE branch = ? AND (layer = 'semantic' OR tag IN ('invariant', 'decision', 'preference'))
            ORDER BY materialized_score DESC LIMIT ?
        """, (brain.current_branch, limit)).fetchall()
    except sqlite3.OperationalError:
        # Fallback for when tag column doesn't exist yet (before migration)
        sem_rows = conn.execute("""
            SELECT 'decision' as tag, content FROM observations 
            WHERE branch = ? AND (layer = 'semantic' OR content LIKE '%[Kind: invariant]%')
            ORDER BY materialized_score DESC LIMIT ?
        """, (brain.current_branch, limit)).fetchall()
    
    clean_diff = normalize_content(diff_output)
    
    # Pattern-based Heuristic Map
    TECH_PATTERNS = {
        "redis": [re.compile(r"\bimport redis\b"), re.compile(r"\bfrom redis\b")],
        "postgres": [re.compile(r"\bpsycopg\b"), re.compile(r"\bpostgres\b"), re.compile(r"\bpostgresql\b")],
        "sqlite": [re.compile(r"\bsqlite3?\b")],
        "fastapi": [re.compile(r"\bfastapi\b"), re.compile(r"\bstarlette\b")],
        "flask": [re.compile(r"\bflask\b"), re.compile(r"\bwerkzeug\b")]
    }
    
    for row in sem_rows:
        fact_tag = row["tag"]
        fact_content = row["content"].lower()
        
        # Formalize rule engine check. 
        # A simple naive rule mapper for demonstration of the pattern engine
        forbidden_tech = []
        if "sqlite" in fact_content and any(w in fact_content for w in ["only", "must", "always"]):
            forbidden_tech = ["redis", "postgres"]
        elif "postgres" in fact_content and any(w in fact_content for w in ["only", "must", "always"]):
            forbidden_tech = ["redis", "sqlite"]
            
        for tech in forbidden_tech:
            for pattern in TECH_PATTERNS.get(tech, []):
                if pattern.search(clean_diff):
                    is_hard = fact_tag == "invariant"
                    penalty = 0.5 if is_hard else 0.2
                    level = ConflictLevel.HARD if is_hard else ConflictLevel.SOFT
                    
                    result.score -= penalty
                    result.issues.append({
                        "type": "alignment", 
                        "message": f"[{level.upper()}] Diff introduces '{tech}' which violates '{fact_content[:40]}...'"
                    })
                    if is_hard:
                        result.status = "block"

    # 4. L3: Documentation Sync Check
    docs_changed = any("AGENTS.md" in f or "README.md" in f for f in staged_files)
    if loc_changed > 30 and not docs_changed:
        result.score -= 0.2
        result.issues.append({"type": "doc_drift", "message": f"Significant code changes ({loc_changed} LOC) without updating AGENTS.md or documentation."})
        result.suggestions.append("Consider updating AGENTS.md to reflect these architectural changes.")

    # 5. L4: Noise Control
    if loc_changed <= 2 and "fix" not in commit_msg.lower():
        result.score -= 0.1
        result.issues.append({"type": "noise", "message": "Commit is very small. Consider squashing if it's part of a larger logical change."})


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
