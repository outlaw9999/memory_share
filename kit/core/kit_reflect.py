import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from kit.core.kit_cognitive_core import SAMBrain, Memory

@dataclass
class Resolution:
    winner_id: Optional[int] = None
    winner_content: str = ""
    reason: str = ""
    is_violation: bool = False
    confidence: float = 0.0
    overridden: List[int] = field(default_factory=list)

@dataclass
class ReflectReport:
    score: float = 1.0
    status: str = "PASS"
    gaps: List[str] = field(default_factory=list)
    drifts: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    confirmations: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    resolutions: Dict[str, Resolution] = field(default_factory=dict)

# Low-level signal patterns: Focusing on imports and dependencies (Infra-grade)
IMPORT_PATTERNS = [
    r'^\s*import\s+([\w\.]+)',
    r'^\s*from\s+([\w\.]+)\s+import',
    r'require\(["\']([\w\.-]+)["\']\)',
    r'use\s+([\w:]+);',  # Rust
    r'extern\s+crate\s+([\w]+)', # Rust
]

def extract_signals(diff_text: str) -> List[str]:
    """
    Extract architectural signals (imports/dependencies) from a diff.
    Limited to 50 signals to maintain < 50ms performance.
    """
    signals = set()
    lines = diff_text.splitlines()
    
    # We only care about added lines (+) or the first 500 lines of a full file
    # For now, let's assume it's a diff or a snippet.
    for line in lines:
        if line.startswith('-'): continue
        clean_line = line.lstrip('+').strip()
        
        for pattern in IMPORT_PATTERNS:
            match = re.search(pattern, clean_line)
            if match:
                signals.add(match.group(1))
        
        if len(signals) >= 50:
            break
            
    return sorted(list(signals))

def calculate_adaptive_score(m: Memory, current_scope: str) -> float:
    """
    Additive scoring model: Stable, non-probabilistic arbitration.
    Score = base_materialized_score + type_bonus + scope_bonus
    """
    # Type bonuses (The Hierarchy)
    type_bonus = 0.0
    if m.tag == 'invariant': type_bonus = 0.3
    elif m.tag == 'decision': type_bonus = 0.2
    elif m.tag == 'preference': type_bonus = 0.1
    
    # Scope bonuses (Locality preference)
    scope_bonus = 0.0
    if m.scope == current_scope:
        scope_bonus = 0.3
    elif current_scope.startswith(m.scope) and m.scope != "":
        scope_bonus = 0.2
    elif m.scope in ["global", "", None]:
        scope_bonus = 0.1
        
    return m.score + type_bonus + scope_bonus

def resolve_cognitive_conflict(memories: List[Memory], current_scope: str, signal: str) -> Resolution:
    """
    The Supreme Court: Deterministic conflict arbitration.
    Ensures Invariant sanctity and explainable scoped refinements.
    """
    if not memories:
        return Resolution(reason=f"GAP: '{signal}' not in memory.", confidence=0.0)
        
    # 1. Filter and Sort Invariants specifically to guard the hierarchy
    invariants = sorted(
        [m for m in memories if m.tag == 'invariant'],
        key=lambda m: calculate_adaptive_score(m, current_scope),
        reverse=True
    )
    
    # 2. Additive Rank all memories
    ranked = sorted(
        memories, 
        key=lambda m: calculate_adaptive_score(m, current_scope), 
        reverse=True
    )
    
    winner = ranked[0]
    losers = ranked[1:]
    winner_score = calculate_adaptive_score(winner, current_scope)
    
    # 3. Calculate Confidence based on margin
    margin = 0.0
    if losers:
        margin = winner_score - calculate_adaptive_score(losers[0], current_scope)
        confidence = margin / (abs(winner_score) + 1e-5)
    else:
        confidence = 1.0
        
    # 4. Constitutional Guardrail: Decision CANNOT override Invariant
    # If the winner is NOT an invariant, but an invariant exists in ANY matched scope
    # (unless the invariant is broader than the winner - actually, the Architect said 
    # Decision can NEVER override Global Invariant).
    if winner.tag != 'invariant' and invariants:
        return Resolution(
            winner_id=invariants[0].id,
            winner_content=invariants[0].content,
            is_violation=True,
            reason=f"CONSTITUTIONAL VIOLATION: Local '{winner.tag}' cannot override Global Invariant '{invariants[0].content}'",
            confidence=1.0,
            overridden=[winner.id] + [l.id for l in losers if l.id != invariants[0].id]
        )
        
    # 5. Explainability
    reason = f"Winner chosen by adaptive score ({winner_score:.2f})."
    if losers:
        reason += f" Overrides {len(losers)} weaker/broader rule(s)."
        if winner.scope == current_scope and losers[0].scope != current_scope:
            reason += " (Reason: Scoped refinement wins)"
            
    return Resolution(
        winner_id=winner.id,
        winner_content=winner.content,
        reason=reason,
        is_violation=False,
        confidence=confidence,
        overridden=[l.id for l in losers]
    )

def run_reflect(brain: SAMBrain, diff_text: str, scope: str = None) -> ReflectReport:
    """
    Main reflection pipeline with Calibration (Consistency Engine v2).
    """
    report = ReflectReport()
    signals = extract_signals(diff_text)
    
    if not signals:
        return report

    current_scope = scope or brain.get_normalized_scope()
    processed_signals = signals[:20]
    
    for signal in processed_signals:
        memories = brain.recall([signal], limit=10, fast=True)
        
        # Arbitrate conflicts
        res = resolve_cognitive_conflict(memories, current_scope, signal)
        report.resolutions[signal] = res
        
        if res.winner_id is None:
            report.gaps.append(signal)
            report.suggestions.append(f"kit learn --uid {signal} --content \"Identify {signal} role in architecture\"")
            continue
            
        if res.is_violation:
            report.violations.append(signal)
        else:
            # Check for Drift (Winner scope mismatch)
            winner_scope = next((m.scope for m in memories if m.id == res.winner_id), "")
            if winner_scope != current_scope and winner_scope not in ["", "global", None]:
                report.drifts.append(signal)
            else:
                report.confirmations.append(signal)

    # Calculate cognitive score
    total = len(processed_signals)
    if total > 0:
        penalty = (len(report.gaps) * 0.2) + (len(report.drifts) * 0.1) + (len(report.violations) * 0.5)
        report.score = max(0.0, 1.0 - penalty)
        
    report.status = "PASS" if report.score > 0.8 else "WARN"
    if report.violations:
        report.status = "BLOCK"
        
    return report
