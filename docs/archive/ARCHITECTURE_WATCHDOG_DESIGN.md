# Architecture Watchdog Design (Tier 3 / Level 8)

**Status**: Designed, not yet implemented  
**Scope**: ~150–200 lines of Python  
**Timeline**: Post-Tier 2 stabilization (1-2 months)

---

## 1. What Is Architecture Watchdog?

**Current Behavior (Reactive)**:
```
Agent asks: "Is AuthService too big?"
→ Agent calls .kit
→ .kit analyzes
→ Agent gets answer
```

**Watchdog Behavior (Proactive)**:
```
Developer commits code
→ Watchdog auto-analyzes architecture impact
→ Watchdog creates PR comment
→ Watchdog notifies architect
```

This is **Continuous Architecture Observability** (like Dependabot for architecture).

---

## 2. Watchdog Architecture

### Components

```
┌─ VCS Webhook (GitHub/GitLab) ─────────────┐
│  onPush, onPR events                      │
└──────────────┬────────────────────────────┘
               │
               ↓
┌─ Watchdog Service ────────────────────────┐
│  1. Fetch changed files                   │
│  2. Run kit_skill_run(investigate)        │
│  3. Evaluate decision_engine rules        │
│  4. Generate comment + alert              │
└──────────────┬────────────────────────────┘
               │
               ↓
┌─ Artifact Generation ─────────────────────┐
│  1. PR Comment (markdown)                 │
│  2. Slack Notification                    │
│  3. Email Alert (architect)               │
│  4. Architecture Ledger (JSON)            │
└───────────────────────────────────────────┘
```

---

## 3. Core Implementation (~150 lines)

### Module: `watchdog_engine.py`

```python
import json
import time
from typing import Dict, Any, List, Optional
from kit_mcp_server import MCPServer
from dataclasses import dataclass

@dataclass
class WatchdogAlert:
    severity: str  # CRITICAL, WARNING, HEALTHY
    modules_affected: List[str]
    issues: List[str]
    next_actions: List[str]
    policy_violations: List[str]
    action_plan: List[str]

class ArchitectureWatchdog:
    
    def __init__(self):
        self.kit = MCPServer()
        self.call_count = 0
        self.alert_threshold = "WARNING"
    
    def analyze_commit(self, 
                       commit_hash: str,
                       changed_files: List[str]) -> Optional[WatchdogAlert]:
        """
        Analyze architecture impact of a commit.
        
        Args:
            commit_hash: Git commit SHA
            changed_files: List of changed file paths
        
        Returns:
            WatchdogAlert if issues found, None if healthy
        """
        
        # 1. Determine analysis scope
        affected_modules = self._extract_modules(changed_files)
        
        if not affected_modules:
            return None  # No code changes (docs/tests only)
        
        # 2. Run .kit skill with signal detail_level
        skill_result = self.kit.handle_kit_skill_run(
            skill_name="architecture_investigate",
            inputs={"changed_files": changed_files},
            detail_level="signal"  # 30 tokens, fast
        )
        
        # 3. Evaluate decision engine output
        signal = skill_result.get("signal", {})
        decisions = skill_result.get("decisions", {})
        next_actions = skill_result.get("next_actions", [])
        
        severity = signal.get("severity", "HEALTHY")
        issues = signal.get("issues", [])
        
        # 4. Determine if alert needed
        if self._should_alert(severity, decisions):
            
            # Fetch full details only if needed
            payload_ref = signal.get("payload_ref")
            if payload_ref:
                full_result = self.kit.handle_kit_payload_get(payload_ref)
                raw_results = full_result.get("payload", {})
            else:
                raw_results = {}
            
            alert = WatchdogAlert(
                severity=severity,
                modules_affected=affected_modules,
                issues=issues,
                next_actions=[a.get("action") for a in next_actions],
                policy_violations=self._extract_violations(decisions),
                action_plan=self._generate_action_plan(
                    severity, 
                    issues, 
                    affected_modules,
                    raw_results
                )
            )
            
            self.call_count += 1
            return alert
        
        return None
    
    def _extract_modules(self, changed_files: List[str]) -> List[str]:
        """Extract module names from file paths."""
        modules = set()
        for filepath in changed_files:
            # auth/service.py → auth.service
            parts = filepath.replace(".py", "").split("/")
            if len(parts) > 1:
                module = ".".join(parts[:-1])
                modules.add(module)
        return list(modules)
    
    def _should_alert(self, severity: str, decisions: Dict) -> bool:
        """Determine if alert should be created."""
        severity_levels = {"HEALTHY": 0, "WARNING": 1, "CRITICAL": 2}
        threshold_level = severity_levels.get(self.alert_threshold, 1)
        actual_level = severity_levels.get(severity, 0)
        
        # Alert if severity >= threshold OR critical policies triggered
        policy_count = len(decisions.get("decisions", []))
        return actual_level >= threshold_level or policy_count > 0
    
    def _extract_violations(self, decisions: Dict) -> List[str]:
        """Extract policy violation descriptions."""
        violations = []
        for decision in decisions.get("decisions", []):
            if decision.get("severity") in ["WARNING", "CRITICAL"]:
                violations.append(f"{decision['policy']}: {decision['reason']}")
        return violations
    
    def _generate_action_plan(self,
                              severity: str,
                              issues: List[str],
                              modules: List[str],
                              raw_results: Dict) -> List[str]:
        """Generate actionable recommendations."""
        actions = []
        
        # Rule 1: Cycles
        if "cycle_detected" in issues:
            actions.append(
                f"Break circular dependency in {modules[0]} "
                f"(check call graph)"
            )
        
        # Rule 2: High gravity
        if "high_gravity" in issues:
            actions.append(
                f"Refactor {modules[0]} (too many dependencies)"
            )
        
        # Rule 3: Layer violation
        if "layer_violation" in issues:
            actions.append(
                f"Align {modules[0]} with architecture layers"
            )
        
        # Default
        if not actions:
            actions.append("Schedule architecture review")
        
        return actions


class WatchdogPRCommentBuilder:
    """Generates GitHub PR comment from alert."""
    
    @staticmethod
    def build_comment(alert: WatchdogAlert, commit_hash: str) -> str:
        """Build markdown PR comment."""
        
        severity_emoji = {
            "CRITICAL": "🔴",
            "WARNING": "🟡",
            "HEALTHY": "🟢"
        }
        
        emoji = severity_emoji.get(alert.severity, "⚪")
        
        comment = f"""
{emoji} **Architecture Analysis** ({commit_hash[:7]})

## Severity: {alert.severity}

### Affected Modules
{''.join([f'- `{m}`' for m in alert.modules_affected[:3]])}

### Issues Detected
{''.join([f'- {issue}' for issue in alert.issues])}

### Policy Violations
{''.join([f'- {v}' for v in alert.policy_violations])}

### Recommendations
1. {alert.action_plan[0] if alert.action_plan else 'Schedule review'}
2. {'Consult with architects' if alert.severity == 'CRITICAL' else 'Plan refactoring'}

---
*Generated by .kit Architecture Watchdog*
"""
        return comment


class WatchdogSlackNotifier:
    """Sends notifications to Slack."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def notify(self, alert: WatchdogAlert, commit_hash: str):
        """Send Slack message."""
        
        color = {
            "CRITICAL": "#FF0000",
            "WARNING": "#FFA500",
            "HEALTHY": "#00FF00"
        }.get(alert.severity, "#808080")
        
        message = {
            "attachments": [{
                "color": color,
                "title": f"Architecture Alert: {alert.severity}",
                "text": f"Commit {commit_hash[:7]}",
                "fields": [
                    {
                        "title": "Modules Affected",
                        "value": ", ".join(alert.modules_affected[:3]),
                        "short": True
                    },
                    {
                        "title": "Issues",
                        "value": "\n".join(f"• {i}" for i in alert.issues),
                        "short": False
                    },
                    {
                        "title": "Action",
                        "value": alert.action_plan[0] if alert.action_plan else "Review needed",
                        "short": False
                    }
                ]
            }]
        }
        
        # In real deployment, POST to webhook_url
        # import requests
        # requests.post(self.webhook_url, json=message)


# Example Usage
if __name__ == "__main__":
    watchdog = ArchitectureWatchdog()
    
    # Simulate commit
    alert = watchdog.analyze_commit(
        commit_hash="abc123def456",
        changed_files=[
            "auth/service.py",
            "auth/middleware.py",
            "tests/auth_test.py"
        ]
    )
    
    if alert:
        print(f"ALERT: {alert.severity}")
        print(f"Modules: {alert.modules_affected}")
        print(f"Issues: {alert.issues}")
        
        # Generate outputs
        comment = WatchdogPRCommentBuilder.build_comment(alert, "abc123")
        print("\nPR Comment:")
        print(comment)
```

---

## 4. Integration Points

### GitHub Actions Workflow

```yaml
name: Architecture Watchdog
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  watchdog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run .kit Watchdog
        run: |
          python watchdog_engine.py \
            --commit-hash ${{ github.event.pull_request.head.sha }} \
            --changed-files ${{ github.event.pull_request.changed_files }}
      
      - name: Comment on PR
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: "${{ env.COMMENT }}"
            })
```

### GitLab CI Pipeline

```yaml
architecture_watchdog:
  stage: test
  script:
    - python watchdog_engine.py
      --commit-hash $CI_COMMIT_SHA
      --changed-files $GIT_DIFF_FILES
  artifacts:
    reports:
      comment_report: architecture-alert.md
```

---

## 5. Alert Thresholds

### Configurable via YAML

```yaml
# .kit/watchdog.yaml
watchdog:
  enabled: true
  alert_on: WARNING  # CRITICAL, WARNING, HEALTHY
  slack_webhook: https://hooks.slack.com/...
  notify_architect: true
  
  rules:
    cycles_detected: CRITICAL
    god_module_detected: WARNING
    layer_violations: WARNING
    high_entropy: WARNING
    
  skip_patterns:
    - tests/**
    - docs/**
    - .github/**
```

---

## 6. Output Artifacts

### 1. PR Comment (GitHub)

```markdown
🟡 **Architecture Analysis** (def456a)

## Severity: WARNING

### Affected Modules
- `auth.service`
- `auth.middleware`

### Issues Detected
- high_gravity (400+ incoming calls)

### Policy Violations
- god_module: Too many dependencies

### Recommendations
1. Break AuthService into smaller components
2. Extract utility functions to new module

---
*Generated by .kit Architecture Watchdog*
```

### 2. Slack Notification

```
🟡 Architecture Alert: WARNING
Commit def456a

Modules Affected: auth.service, auth.middleware
Issues: high_gravity
Action: Break AuthService into smaller components
```

### 3. Email Summary (Optional)

```
Subject: Architecture Alert [WARNING] - Commit def456a

Architect,

The following commit triggers architecture warnings:

Modules: auth.service
Issues: High module gravity (400+ dependencies)

Please review the PR and approve/request changes.

---
.kit Watchdog
```

### 4. Architecture Ledger (JSON)

```json
{
  "timestamp": "2026-03-10T15:30:00Z",
  "commit_hash": "def456a",
  "severity": "WARNING",
  "modules_affected": ["auth.service", "auth.middleware"],
  "issues": ["high_gravity"],
  "violations": ["god_module"],
  "actions": ["Break AuthService into smaller components"],
  "resolution": "PENDING"
}
```

---

## 7. Decision Logic

### When to Alert

```python
def should_alert:
    if severity >= alert_threshold:
        return True
    
    if policy_violations > 0:
        # Even HEALTHY can trigger if policies violated
        return True
    
    if "CRITICAL" in policy_severities:
        # Always alert on critical policies
        return True
    
    return False
```

---

## 8. Real-World Workflow

### Scenario: Engineer submits PR

```
1️⃣ Developer pushes commit (auth/service.py modified)
   ↓
2️⃣ GitHub Web Hook triggers watchdog
   ↓
3️⃣ Watchdog extracts changed files: [auth/service.py]
   ↓
4️⃣ Watchdog calls .kit_skill_run(investigate, detail_level=signal)
   ↓
5️⃣ Signal returns: severity=WARNING, issue=high_gravity
   ↓
6️⃣ Watchdog generates PR comment + Slack alert
   ↓
7️⃣ GitHub comments: "AuthService gravity is high, consider splitting"
   ↓
8️⃣ Slack notifies #architecture: "Warning on PR #1234"
   ↓
9️⃣ Architect reviews, approves, or requests changes
   ↓
🔟 Post-merge, ledger records the commit
```

---

## 9. Implementation Timeline

### Week 1: Core Engine
- [x] WatchdogAlert dataclass
- [x] ArchitectureWatchdog class
- [x] analyze_commit() method
- [x] Decision logic

### Week 2: Notifications
- [ ] PR comment builder
- [ ] Slack integration
- [ ] Email templates
- [ ] Ledger recording

### Week 3: CI/CD
- [ ] GitHub Actions workflow
- [ ] GitLab CI integration
- [ ] Webhook configuration
- [ ] Testing

### Week 4: Polish
- [ ] Error handling
- [ ] Logging
- [ ] Documentation
- [ ] Performance tuning

---

## 10. Comparison with Existing Tools

| Tool | Purpose | Our Watchdog |
|------|---------|--------------|
| Dependabot | Dependency updates | Architecture changes |
| SonarQube | Code quality | Architecture structure |
| GitHub Copilot | Code generation | Architecture governance |
| Snyk | Security | Architecture impact |

Watchdog fills gap: **Architecture-specific change monitoring**.

---

## 11. Success Metrics

Once deployed, measure:

- **Alert precision**: >90% of alerts are actionable
- **Alert recall**: >80% of architectural issues caught
- **Response time**: <30s from commit to notification
- **False positive rate**: <10%
- **Architect satisfaction**: >90%

---

## 12. Strategic Value

Watchdog enables:

```
.kit as Continuous Architecture Governance
```

Instead of:
- Quarterly reviews
- Manual audits
- Surprise refactoring

With watchdog:
- Real-time governance
- Automated checks
- Preventive (not reactive)
- Scalable to 1000s of commits/day

---

## 13. Post-Tier-2 Checklist

Before implementing Watchdog:

- [x] Tier 2 stable (ToolBroker, Decision Engine)
- [x] Token compression verified (30× target)
- [x] Multi-agent testing complete
- [ ] Signal accuracy >90% (need 2-4 weeks data)
- [ ] PR comment format validated with real teams
- [ ] CI/CD integration tested
- [ ] Slack/Email templates refined

---

## 14. Conclusion

**Architecture Watchdog** (L8) is the natural evolution of `.kit`:

```
L7: Reactive (Agent asks → .kit answers)
L8: Proactive (Code changes → .kit alerts)
```

This makes `.kit` not just a **tool** or **coprocessor**, but **continuous governance layer**.

**Timeline**: Post-stabilization (1-2 months)  
**Effort**: ~200 lines + CI/CD config  
**Benefit**: 10× increase in architectural accountability  
**Status**: Ready for deployment after Tier 2 proves itself

---

**Next**: Monitor Tier 2 in production → collect metrics → design Watchdog integration
