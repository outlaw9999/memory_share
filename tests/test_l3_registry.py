import sys
import os

sys.path.insert(0, os.getcwd())

from kit.core.l3_registry import (
    L3Rule,
    RuleSeverity,
    RULES,
    MANDATORY_RULES,
    RECOMMENDED_RULES,
    get_rule_by_id,
    get_all_rules,
    get_mandatory_rules,
    get_recommended_rules,
    export_rules_for_extraction,
    get_compliance_score,
    VERSION,
)


def test_l3_version():
    """Test L3 version."""
    assert VERSION == "v0.1.0"
    print("[PASS] L3 version")


def test_rules_count():
    """Test total rules count."""
    assert len(get_all_rules()) == 6
    print("[PASS] Rules count: 6")


def test_mandatory_rules():
    """Test mandatory rules."""
    assert len(MANDATORY_RULES) == 4

    mandatory_ids = {"L3-SQL-001", "L3-AUTH-001", "L3-MEM-001", "L3-ENC-001"}
    assert set(MANDATORY_RULES.keys()) == mandatory_ids
    print("[PASS] Mandatory rules: 4")


def test_recommended_rules():
    """Test recommended rules."""
    assert len(RECOMMENDED_RULES) == 2

    recommended_ids = {"L3-VAL-001", "L3-SAN-001"}
    assert set(RECOMMENDED_RULES.keys()) == recommended_ids
    print("[PASS] Recommended rules: 2")


def test_sql_safety_rule():
    """Test SQL safety rule exists."""
    rule = get_rule_by_id("L3-SQL-001")

    assert rule is not None
    assert rule.name == "Parameterized Query Requirement"
    assert rule.severity == RuleSeverity.MANDATORY
    print("[PASS] SQL safety rule")


def test_auth_guard_rule():
    """Test AUTH guard rule."""
    rule = get_rule_by_id("L3-AUTH-001")

    assert rule is not None
    assert "auth" in rule.name.lower()
    print("[PASS] AUTH guard rule")


def test_memory_rule():
    """Test memory isolation rule."""
    rule = get_rule_by_id("L3-MEM-001")

    assert rule is not None
    assert "workspace" in rule.name.lower() or "memory" in rule.name.lower()
    print("[PASS] Memory isolation rule")


def test_encoding_rule():
    """Test encoding rule."""
    rule = get_rule_by_id("L3-ENC-001")

    assert rule is not None
    assert "utf" in rule.description.lower() or "encoding" in rule.description.lower()
    print("[PASS] Encoding normalization rule")


def test_export_format():
    """Test export format."""
    export = export_rules_for_extraction()

    assert "version" in export
    assert "rules" in export
    assert export["version"] == "v0"
    assert export["rules_count"] == 6
    print("[PASS] Export format")


def test_compliance_score():
    """Test compliance score calculation."""
    score = get_compliance_score(["L3-SQL-001", "L3-AUTH-001"])

    assert "mandatory_compliance" in score
    assert "overall_score" in score
    print("[PASS] Compliance score")


def test_rule_severity():
    """Test rule severity enum."""
    assert RuleSeverity.MANDATORY == "mandatory"
    assert RuleSeverity.RECOMMENDED == "recommended"
    assert RuleSeverity.ADVISORY == "advisory"
    print("[PASS] Rule severity enum")


def test_rule_to_dict():
    """Test rule serialization."""
    rule = get_rule_by_id("L3-SQL-001")
    assert rule is not None

    d = rule.to_dict()

    assert "id" in d
    assert "name" in d
    assert "description" in d
    assert d["id"] == "L3-SQL-001"
    print("[PASS] Rule to_dict")


def test_get_mandatory_rules_list():
    """Test get_mandatory_rules returns list."""
    rules = get_mandatory_rules()

    assert isinstance(rules, list)
    assert len(rules) == 4
    print("[PASS] get_mandatory_rules list")


def test_get_recommended_rules_list():
    """Test get_recommended_rules returns list."""
    rules = get_recommended_rules()

    assert isinstance(rules, list)
    assert len(rules) == 2
    print("[PASS] get_recommended_rules list")


if __name__ == "__main__":
    tests = [
        test_l3_version,
        test_rules_count,
        test_mandatory_rules,
        test_recommended_rules,
        test_sql_safety_rule,
        test_auth_guard_rule,
        test_memory_rule,
        test_encoding_rule,
        test_export_format,
        test_compliance_score,
        test_rule_severity,
        test_rule_to_dict,
        test_get_mandatory_rules_list,
        test_get_recommended_rules_list,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
