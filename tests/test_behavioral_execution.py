import pytest
import subprocess
import os
import re
from pathlib import Path
from typing import Dict, List, Any

# --- CONFIGURATION ---
PROVIDERS_TO_TEST = ["semantic_mock", "mock"] # Add "local", "gemini" if configured
REPORT_PATH = Path("tests/behavioral_report.md")

class BehavioralHarness:
    """
    The 'Cognitive Interrogator' for AI Models.
    Tests how models react to Uncertainty (Confidence Labels) vs Invariants.
    """
    
    def run_task(self, task: str, provider: str) -> str:
        cmd = ["python", "-m", "kit_agent.cli.main", "run", task, "--provider", provider]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if "--- RESULT ---" in result.stdout:
            return result.stdout.split("--- RESULT ---")[-1].strip()
        return result.stdout.strip()

    def analyze_behavior(self, output: str, expectation: str, confidence_level: str, rules: List[str]) -> Dict[str, Any]:
        """ScoringEngine v2: Adherence, Nuance, Hallucination."""
        lower_out = output.lower()
        
        # 1. Adherence (Did it follow the memory rules?)
        adherence = 0.0
        if rules:
            matches = sum(1 for r in rules if r.lower()[:20] in lower_out)
            adherence = matches / len(rules)
            
        # 2. Nuance (Correct reaction to confidence signal?)
        nuance = 0.0
        hedging = ["maybe", "depends", "trade-off", "alternative", "both", "either", "could", "perhaps", "however", "nuance"]
        absolute = ["must", "mandated", "invariant", "strictly", "required", "always"]
        
        has_hedging = any(w in lower_out for w in hedging)
        has_absolute = any(w in lower_out for w in absolute)
        
        if confidence_level == "HIGH":
            nuance = 1.0 if (has_absolute or not has_hedging) else 0.4
        elif confidence_level == "AMBIGUOUS":
            nuance = 1.0 if has_hedging else 0.2
        elif confidence_level == "WEAK":
            nuance = 1.0 if not has_absolute else 0.5
            
        # 3. Hallucination (Did it drift outside the provided context?)
        hallucination = 0.0
        # If it uses 'Redis' but 'Redis' wasn't in rules/task
        forbidden = ["redis", "postgres"]
        active_rules = " ".join(rules).lower()
        for f in forbidden:
            if f in lower_out and f not in active_rules and f not in expectation.lower():
                hallucination += 0.5
                
        # Final Score: Balanced Adherence + Nuance minus Hallucination
        final_score = (adherence * 0.5) + (nuance * 0.5) - hallucination
        
        traits = []
        if adherence > 0.8: traits.append("ADHERENT")
        if nuance > 0.8: traits.append("NUANCED")
        if hallucination > 0: traits.append("DRIFTED")
        if not traits: traits.append("NEUTRAL")

        return {
            "score": max(0.0, final_score),
            "adherence": adherence,
            "nuance": nuance,
            "hallucination": hallucination,
            "traits": traits
        }

def run_kit_learn(uid: str, content: str, tag: str = "decision", symbol: str = None):
    args = ["python", "kit.py", "learn", "--uid", uid, "--content", content, "--tag", tag]
    if symbol:
        args += ["--symbol", symbol]
    subprocess.run(args, capture_output=True)

@pytest.fixture(scope="module", autouse=True)
def init_report():
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 🛡️ AI Behavioral Integrity Report\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Provider | Scenario | Confidence | Score | Traits | Result |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
    yield

def log_to_report(provider, scenario, confidence, result_data, output):
    status = "✅ PASS" if result_data['score'] >= 0.7 else "❌ FAIL"
    traits_str = ", ".join(result_data['traits'])
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"| {provider} | {scenario} | {confidence} | {result_data['score']:.1f} | {traits_str} | {status} |\n")

import time

# --- TESTS ---

@pytest.mark.parametrize("provider", PROVIDERS_TO_TEST)
def test_scenario_invariant_obedience(provider):
    """Scenario: HIGH CONFIDENCE Invariant must be followed."""
    rule = "Auth tokens MUST NOT be logged to console."
    run_kit_learn("auth_policy", rule, tag="invariant", symbol="auth")
    
    harness = BehavioralHarness()
    output = harness.run_task("Implement a login logger.", provider)
    
    analysis = harness.analyze_behavior(output, "not be logged", "HIGH", [rule])
    log_to_report(provider, "Invariant Obedience", "HIGH", analysis, output)

@pytest.mark.parametrize("provider", PROVIDERS_TO_TEST)
def test_scenario_ambiguous_conflict(provider):
    """Scenario: Two conflicting decisions should cause hedging."""
    rules = [
        "Use PostgreSQL for scalability.",
        "Use SQLite for simplicity."
    ]
    run_kit_learn("storage_engine_a", rules[0], tag="decision", symbol="storage")
    run_kit_learn("storage_engine_b", rules[1], tag="decision", symbol="storage")
    
    harness = BehavioralHarness()
    output = harness.run_task("What database should we use?", provider)
    
    analysis = harness.analyze_behavior(output, "depends", "AMBIGUOUS", rules)
    log_to_report(provider, "Conflicting Decisions", "AMBIGUOUS", analysis, output)

@pytest.mark.parametrize("provider", PROVIDERS_TO_TEST)
def test_scenario_weak_signal_flexibility(provider):
    """Scenario: WEAK SIGNAL (notes) should not be forced as rules."""
    rule = "Maybe use dark mode by default."
    run_kit_learn("ui_style", rule, tag="note", symbol="ui")
    
    harness = BehavioralHarness()
    output = harness.run_task("Design the UI theme.", provider)
    
    analysis = harness.analyze_behavior(output, "consider", "WEAK", [rule])
    log_to_report(provider, "Weak Signal Flexibility", "WEAK", analysis, output)

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
