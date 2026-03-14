# `.kit` Skills Framework Specification

**Version**: 1.0  
**Status**: Spec (non-breaking enhancement to v1.0)  
**Date**: 2026-03-10  

---

## Overview

Skills are **high-level diagnostic workflows** that compose multiple diagnostic stones into reusable patterns. They sit **above MCP tools** and enable agents to invoke multi-step analysis in one call.

Skills enable:
- 🎯 **Agent autonomy** — declare intent, not steps
- 📉 **Token efficiency** — compose relevant stones only
- 🔄 **Reusability** — share patterns across projects
- 🛠️ **Discoverability** — MCP exposes all available skills

---

## Skill Definition Format

Each skill is a YAML file: `.kit/skills/<name>.yaml`

```yaml
# Metadata
name: architecture_investigate          # Unique name
version: 1                              # Major version (for backward compat tracking)
schema_version: 1                       # Skills schema version (frozen for compat)
description: "Full architecture health check with actionable insights"
author: ".kit"
tags: [health, architecture, agent-primary]
cost: medium                            # Execution cost: low, medium, high
depends_on: []                          # Other skills (optional dependencies)

# Input contract
inputs:
  - name: depth
    type: suggest["quick", "thorough"]
    default: quick
    description: "Analysis depth level"

# Composition: which stones to run
uses:
  - stone: doctor                        # Built-in stone
  - stone: gravity
  - stone: hotspots
  - stone: cycles

# Interpretation rules (for agent)
interpretation:
  rules:
    - if: cycles_detected > 0
      then: severity = CRITICAL
      reason: "Circular dependencies block refactoring"
    
    - if: gravity_top_modules >= 5
      then: severity = WARNING
      reason: "High architectural complexity"
    
    - if: hotspots_risky_count > 0
      then: severity = WARNING
      recommendation: "Schedule code review for hotspots"

  activation_level:
    hot: ["cycles detected", "layer violations", "critical hotspots"]
    warm: ["high gravity", "many dependencies"]
    cold: ["all metrics healthy"]

# Output structure (what agent expects)
output:
  type: object
  schema:
    results: object                     # Per-stone results
    severity: enum[CRITICAL, WARNING, HEALTHY]
    recommendations: list[string]
    activation_level: enum[hot, warm, cold]

# Agent context
agent_context:
  when_to_invoke: "Whenever analyzing codebase health"
  input_prompt: "Analyze this codebase's architecture"
  output_instructions: |
    If severity is CRITICAL, stop and explain cycles.
    Prioritize hotspots recommendations for next PR.
  estimated_tokens: 300-800
  timeout_seconds: 30
```

---

## Field Reference

### Metadata
| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `name` | string | ✅ | Unique skill identifier (snake_case) |
| `version` | integer | ✅ | Skill major version (1, 2, etc.) |
| `schema_version` | integer | ❌ | Skills schema version (default: 1) |
| `description` | string | ✅ | One-line purpose |
| `author` | string | ❌ | Creator (default: ".kit") |
| `tags` | list[string] | ❌ | Keywords for discovery |
| `cost` | enum[low, medium, high] | ❌ | Execution cost (low, medium, high) |
| `depends_on` | list[string] | ❌ | Other skills this requires |

### inputs
List of input parameters. Each has:
| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `name` | string | ✅ | Parameter name |
| `type` | enum[text, suggest, number] | ✅ | Input type |
| `default` | any | ❌ | Default value |
| `description` | string | ✅ | What this parameter does |

**type** values:
- `text` — free user input
- `suggest[opt1, opt2]` — agent chooses from options
- `number` — numeric parameter

### uses
List of diagnostic stones to compose. Each has:
| Field | Type | Required |
|-------|------|----------|
| `stone` | string | ✅ |
| `args` | object | ❌ |
| `required` | bool | ❌ |

Example:
```yaml
uses:
  - stone: doctor                        # Optional (runs if requested)
  - stone: gravity                       # Required by default
    args:
      limit: 10
  - stone: impact
    required: true
```

### interpretation
Logical rules that guide agent reasoning. Contains:

**rules** — If-then clauses:
```yaml
rules:
  - if: gravity_top_modules >= 5        # Boolean expression
    then: severity = WARNING            # Assignment
    reason: "Justification"
    recommendation: "Action to take"
```

**activation_level** — Categorizes metric urgency:
```yaml
activation_level:
  hot: [list of high-priority findings]
  warm: [medium-priority]
  cold: [low-priority]
```

### output
**FROZEN Output Schema** (standardized for all skills):

```yaml
output:
  type: object
  schema:
    skill: string                 # Skill name that was executed
    version: integer              # Skill version executed
    severity: enum[CRITICAL, WARNING, HEALTHY]
    summary: string               # One-line summary for agent
    findings: list[string]        # Key findings
    recommendations: list[string] # Actionable recommendations
    activation_level: enum[hot, warm, cold]
    confidence: number            # 0-1, how confident is this result
    results: object               # Raw stone results (optional, for transparency)
    cost_estimate: enum[low, medium, high]
    execution_time_ms: number     # How long skill took to run
```

**Why Frozen**: Agents parse this structure. Changes require schema_version bump.

### agent_context
Instructions for LLM invoking this skill:
| Field | Type | Purpose |
|-------|------|---------|
| `when_to_invoke` | string | Trigger conditions |
| `input_prompt` | string | Suggested user prompt |
| `output_instructions` | string | How to interpret results |
| `estimated_tokens` | string | Budget guidance |
| `timeout_seconds` | number | Query timeout |

---

## Discovery Protocol

Agents discover skills via `kit_skills_list` MCP tool:

```json
{
  "method": "tools/call",
  "params": {
    "name": "kit_skills_list",
    "arguments": {}
  }
}
```

Response:
```json
{
  "status": "success",
  "result": {
    "skills": [
      {
        "name": "architecture_investigate",
        "version": "1.0",
        "description": "...",
        "tags": ["health", "architecture"],
        "estimated_tokens": "300-800"
      }
    ]
  }
}
```

---

## Skill Lifecycle

### Installation
Skills are discovered **automatically** from `.kit/skills/` directory.

### Invocation
Agent calls skill via new `kit_skill_run` MCP tool:

```json
{
  "name": "kit_skill_run",
  "arguments": {
    "skill_name": "architecture_investigate",
    "inputs": {
      "depth": "thorough"
    }
  }
}
```

### Execution
1. Validate inputs against schema
2. Load skill YAML
3. Execute each stone in `uses` list
4. Apply interpretation rules
5. Return structured result

---

## Skill Versioning & Backward Compatibility

### version Field (Skill Version)
```yaml
version: 1     # Current version of THIS skill
```

- Bumped when skill changes (uses, interpretation, output)
- Agents can request specific version: `kit_skill_run(..., skill_version=1)`
- Non-breaking: only add new recommendations, never remove

### schema_version Field (Skills Framework Version)
```yaml
schema_version: 1    # Version of skills spec this uses
```

- Fixed at 1 for all v1.x skills
- Skills framework evolution tracked separately
- Gate future features: only v1 skills use v1 schema

### Compatibility Rules

**Never (Breaking)**:
- Change skill name
- Change output schema structure
- Remove stones from `uses:`

**OK (Non-breaking)**:
- Add new recommendations
- Add new interpretation rules
- Increase version number
- Change cost estimate

**Example**: If you need to break a skill, create new one:
```
architecture_investigate (v1)
architecture_investigate_v2 (v2)    # New, separate skill
```

---

Skills layer is **transparent** to existing `.kit v1.0`:
- ✅ No changes to frozen CLI (kit doctor, kit query, etc.)
- ✅ No changes to stone output format
- ✅ MCP tools backward compatible
- ✅ Opt-in for agents

Agents can:
- Use skills for convenience (**recommended**)
- Call stones directly if preferred
- Mix both approaches

---

## Skill Dependencies & Execution Graph

### depends_on Field

Skills can declare dependencies on other skills:

```yaml
name: architecture_review_comprehensive
version: 1
depends_on:
  - architecture_investigate
  - architecture_summary
```

### Execution Order

When agent runs a skill with dependencies:

```
1. Validate all dependencies exist
2. Run dependencies in order (with caching)
3. Inject dependency results into current skill
4. Run current skill with enhanced context
```

### Example Workflow

**Agent calls**: `kit_skill_run(architecture_review_comprehensive)`

**MCP executes**:
```
1. Run architecture_investigate → cache results
2. Run architecture_summary → cache results
3. Use both in architecture_review_comprehensive
4. Return final result
```

**Agent reads** one JSON with full context already analyzed.

### Cost Optimization

Agent can skip dependencies if cost is high:

```python
response = mcp_call("kit_skill_run", 
                    skill="architecture_review_comprehensive",
                    skip_dependencies=True)    # Skip if you have results already
```

---

```yaml
name: architecture_investigate
version: 1.0
description: "Full architecture health check with actionable insights"
tags: [health, architecture, agent-primary]

inputs:
  - name: depth
    type: suggest[quick, thorough]
    default: quick

uses:
  - stone: doctor
  - stone: gravity
  - stone: hotspots
  - stone: cycles

interpretation:
  rules:
    - if: cycles_detected > 0
      then: severity = CRITICAL
      reason: "Circular dependencies prevent refactoring"
    - if: gravity_top_modules >= 5
      then: severity = WARNING
      recommendation: "Schedule architectural review"

  activation_level:
    hot: ["cycles detected", "layer violations"]
    warm: ["high gravity"]
    cold: ["metrics healthy"]

agent_context:
  when_to_invoke: "Codebase health analysis"
  input_prompt: "Investigate this codebase's architecture"
  estimated_tokens: "300-800"
  timeout_seconds: 30
```

---

## Design Rationale

### Why YAML?
- Human-readable (skill authors are developers)
- No Turing-completeness (can't encode arbitrary logic)
- Composable (reuse stone definitions)
- Agent-parseable (structured for LLM reasoning)

### Why Not Cowork Skills?
- Cowork is **agent orchestration layer** (external)
- `.kit` skills are **diagnostic layer** (internal)
- Kit skills work standalone, with or without Cowork

### Why Not JSON?
- JSON less natural for human skill authors
- YAML comments support documentation
- YAML indentation enforces clarity

### Why activation_level?
- Brain v2 filters by hot/warm/cold
- Agents can prioritize analysis (hop/skip cold diagnostics)
- Reduces token overhead without losing information

---

## Future Extensions (v1.1+)

Possible (non-breaking):
- [ ] Conditional stone execution (`if_metric_warning`)
- [ ] Custom prompts per stone
- [ ] Skill dependencies (`requires: [other_skill]`)
- [ ] Async stone execution
- [ ] Parameterized stone arguments

**NOT planned** (would require v2.0):
- Turing-complete skill language
- Arbitrary Python execution
- Breaking changes to stone interface
