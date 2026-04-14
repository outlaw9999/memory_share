"""
L3 Seed Registry v0 - Abstract Safety Kernel

This module defines the minimal cognitive kernel for cross-repo pattern extraction.
L3 is NOT a database - it is a constraint system for abstraction.

Contents:
- abstraction_rules: Pattern-level truths (no repo binding)
- safety_principles: Security invariants
- encoding_policy: File normalization rules
- memory_isolation_rules: Workspace scoping

IMPORTANT: L3 DOES NOT contain:
- SQL_12 / AUTH_01 cases
- Repo-specific corpus
- Runtime signals
- Implementation details
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RuleSeverity(StrEnum):
    """Severity level for L3 rules."""

    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    ADVISORY = "advisory"


@dataclass
class L3Rule:
    """Abstract rule for cross-repo pattern extraction."""

    id: str
    name: str
    description: str
    severity: RuleSeverity
    rationale: str
    anti_pattern: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "rationale": self.rationale,
            "anti_pattern": self.anti_pattern,
        }


# ═══════════════════════════════════════════════════════════════════════════════════════
# L3 SEED RULES (v0 - MINIMAL)
# ═══════════════════════════════════════════════════════════════════════════════════════════════

SQL_SAFETY_RULE = L3Rule(
    id="L3-SQL-001",
    name="Parameterized Query Requirement",
    description="SQL queries MUST use parameterized interface, never string interpolation in execution loops",
    severity=RuleSeverity.MANDATORY,
    rationale="String interpolation enables SQL injection. Pattern extraction must enforce parameterized queries.",
    anti_pattern="""
        ❌ AVOID:
        for item in items:
            query = f"SELECT * FROM users WHERE id = {item}"
            cursor.execute(query)
        
        ✅ REQUIRE:
        cursor.execute("SELECT * FROM users WHERE id = ?", (item,))
    """,
)

AUTH_GUARD_RULE = L3Rule(
    id="L3-AUTH-001",
    name="Explicit Authentication Guard",
    description="All external routes MUST enforce authentication before execution boundary",
    severity=RuleSeverity.MANDATORY,
    rationale="Unguarded routes expose internal services to unauthorized access.",
    anti_pattern="""
        ❌ AVOID:
        @app.route("/admin/delete")
        def delete_all():
            # No auth check
            return db.drop_all()
        
        ✅ REQUIRE:
        @app.route("/admin/delete")
        @require_auth
        def delete_all():
            return db.drop_all()
    """,
)

MEMORY_ISOLATION_RULE = L3Rule(
    id="L3-MEM-001",
    name="Workspace-Scoped Memory",
    description="Memory MUST be scoped by workspace identity, not runtime path",
    severity=RuleSeverity.MANDATORY,
    rationale="Path-based scoping breaks when repo is moved or renamed.",
    anti_pattern="""
        ❌ AVOID:
        memory = get_memory(abs_path)
        
        ✅ REQUIRE:
        workspace_id = hash(git_root + origin_url)
        memory = get_scoped_memory(workspace_id)
    """,
)

ENCODING_NORMALIZATION_RULE = L3Rule(
    id="L3-ENC-001",
    name="UTF-8 Input Normalization",
    description="All file inputs MUST be normalized to UTF-8 before semantic processing",
    severity=RuleSeverity.MANDATORY,
    rationale="Mixed encoding causes semantic drift and false positives in pattern detection.",
    anti_pattern="""
        ❌ AVOID:
        with open(filepath) as f:
            content = f.read()
        
        ✅ REQUIRE:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        
        Or use chardet for detection:
        detector = Universal_chardet()
        result = detector.detect(filepath)
        content = result.raw.decode("utf-8")
    """,
)

INPUT_VALIDATION_RULE = L3Rule(
    id="L3-VAL-001",
    name="Input Schema Validation",
    description="External inputs MUST be validated against schema before processing",
    severity=RuleSeverity.RECOMMENDED,
    rationale="Unvalidated input is the primary attack vector.",
    anti_pattern="""
        ❌ AVOID:
        def process(data):
            return data["key"]  # No validation
        
        ✅ REQUIRE:
        from pydantic import BaseModel
        class Input(BaseModel):
            key: str
        
        def process(data: Input):
            return data.key
    """,
)

RUNTIME_SANDBOX_RULE = L3Rule(
    id="L3-SAN-001",
    name="Execution Sandbox",
    description="External code execution MUST be isolated in sandbox",
    severity=RuleSeverity.RECOMMENDED,
    rationale="Unrestricted execution can compromise the runtime environment.",
    anti_pattern="""
        ❌ AVOID:
        exec(user_code)
        
        ✅ REQUIRE:
        import restrictedpython
        restrictedpython.safe_exec(user_code)
        
        Or use subprocess with limited permissions:
        subprocess.run([sys.executable, script], restrict=True)
    """,
)


# ═══════════════════════════════════════════════════════════════════════════════════════
# RULE REGISTRY (v0)
# ═══════════════════════════════════════════════════════════════════════════════════════

RULES: dict[str, L3Rule] = {
    "L3-SQL-001": SQL_SAFETY_RULE,
    "L3-AUTH-001": AUTH_GUARD_RULE,
    "L3-MEM-001": MEMORY_ISOLATION_RULE,
    "L3-ENC-001": ENCODING_NORMALIZATION_RULE,
    "L3-VAL-001": INPUT_VALIDATION_RULE,
    "L3-SAN-001": RUNTIME_SANDBOX_RULE,
}

MANDATORY_RULES = {rule_id: rule for rule_id, rule in RULES.items() if rule.severity == RuleSeverity.MANDATORY}

RECOMMENDED_RULES = {rule_id: rule for rule_id, rule in RULES.items() if rule.severity == RuleSeverity.RECOMMENDED}


# ═══════════════════════════════════════════════════════════════════════════════════════
# EXTRACTION HELPERS
# ═══════════════════════════════════════════════════════════���═══════════════════════════


def get_mandatory_rules() -> list[L3Rule]:
    """Return all mandatory rules."""
    return list(MANDATORY_RULES.values())


def get_recommended_rules() -> list[L3Rule]:
    """Return all recommended rules."""
    return list(RECOMMENDED_RULES.values())


def get_all_rules() -> list[L3Rule]:
    """Return all L3 seed rules."""
    return list(RULES.values())


def get_rule_by_id(rule_id: str) -> L3Rule | None:
    """Get rule by ID."""
    return RULES.get(rule_id)


def export_rules_for_extraction() -> dict[str, Any]:
    """Export rules in safe format for cross-repo extraction."""
    return {
        "version": "v0",
        "source": "L3 seed registry",
        "rules_count": len(RULES),
        "rules": [rule.to_dict() for rule in RULES.values()],
        "mandatory_count": len(MANDATORY_RULES),
        "recommended_count": len(RECOMMENDED_RULES),
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# VALIDATION INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════════════


def validate_against_rule(
    _code_snippet: str,
    rule_id: str,
) -> tuple[bool, str]:
    """
    Validate code snippet against a rule.

    Returns (passes, reason) tuple.
    This is a placeholder - real validation requires AST analysis per language.
    """
    rule = get_rule_by_id(rule_id)
    if not rule:
        return False, f"Rule {rule_id} not found"

    if rule.anti_pattern:
        if "❌ AVOID" in rule.anti_pattern:
            return True, "Manual review required - check anti_pattern"

    return True, "Validated"


def get_compliance_score(code_rules: list[str]) -> dict[str, Any]:
    """
    Calculate compliance score for a set of rules.

    Args:
        code_rules: List of rule IDs that the code follows

    Returns compliance report.
    """
    mandatory_hit = sum(1 for rid in code_rules if rid in MANDATORY_RULES)
    recommended_hit = sum(1 for rid in code_rules if rid in RECOMMENDED_RULES)

    total_mandatory = len(MANDATORY_RULES)
    total_recommended = len(RECOMMENDED_RULES)

    mandatory_score = mandatory_hit / total_mandatory if total_mandatory else 0
    recommended_score = recommended_hit / total_recommended if total_recommended else 0
    overall_score = (mandatory_score * 0.7) + (recommended_score * 0.3)

    return {
        "mandatory_compliance": f"{mandatory_hit}/{total_mandatory}",
        "recommended_compliance": f"{recommended_hit}/{total_recommended}",
        "overall_score": round(overall_score, 2),
        "status": "compliant" if mandatory_score == 1.0 else "partial",
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# SEED VERSION INFO
# ═══════════════════════════════════════════════════════════════════════════════════════

VERSION = "v0.1.0"
SEED_DATE = "2024-01-01"

__all__ = [
    "L3Rule",
    "RuleSeverity",
    "RULES",
    "MANDATORY_RULES",
    "RECOMMENDED_RULES",
    "get_mandatory_rules",
    "get_recommended_rules",
    "get_all_rules",
    "get_rule_by_id",
    "export_rules_for_extraction",
    "validate_against_rule",
    "get_compliance_score",
    "VERSION",
]
