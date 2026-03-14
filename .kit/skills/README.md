# `.kit/skills/` — Diagnostic Skills Framework

**Version**: 1.0 (Complementary to .kit v1.0)

Skills are **high-level diagnostic workflows** that compose multiple diagnostic stones into reusable patterns for AI agents.

---

## Directory Contents

| File | Purpose |
|------|---------|
| **SPEC.md** | Complete skill definition specification (YAML schema, field reference) |
| **architecture_summary.yaml** | Quick overview skill (entry point for agents) |
| **architecture_investigate.yaml** | Full health check skill with insights |
| **architecture_review.yaml** | PR impact assessment skill |

---

## Quick Start for Agents

### 1. Discover Skills (MCP)

```json
{
  "name": "kit_skills_list",
  "arguments": {}
}
```

Returns: List of all available skills with metadata

### 2. Run a Skill (MCP)

```json
{
  "name": "kit_skill_run",
  "arguments": {
    "skill_name": "architecture_summary",
    "inputs": {"include_metrics": "essential"}
  }
}
```

Returns: Composed stone results + interpreted findings + recommendations

---

## Skill Lifecycle

### For Skill Authors

1. **Define** — Create YAML file in `.kit/skills/`
2. **Schema** — Follow SPEC.md format
3. **Compose** — List stones to execute in `uses:` section
4. **Interpret** — Add rules and activation levels
5. **Test** — `kit_skill_run` will load and execute
6. **Share** — Commit to repository

### For AI Agents

1. **Discover** — `kit_skills_list` to see available skills
2. **Understand** — Read skill description + estimated tokens
3. **Invoke** — `kit_skill_run` with skill name + inputs
4. **Interpret** — Use severity + recommendations + activation_level to decide next steps

---

## Design Philosophy

### Skills are NOT

- ❌ Python plugins (no code execution)
- ❌ Turing-complete (no arbitrary logic)
- ❌ Replacing stones (complementary, composable)
- ❌ Agent-aware (work with any agent, CLI, or script)

### Skills ARE

- ✅ Reusable workflows (compose multiple stones)
- ✅ Human-readable (YAML, comments, clear intent)
- ✅ Agent-parseable (structured for LLM reasoning)
- ✅ Lightweight (< 50 lines each, typically)
- ✅ Self-documenting (metadata + interpretation rules)

---

## Adding New Skills

### Pattern: 5-Step Skill Design

1. **Name** — Clear, action-oriented (architecture_*, performance_*, etc.)
2. **Purpose** — One-line description of intent
3. **Stones** — Which diagnostics to compose (in `uses:`)
4. **Rules** — If-then interpretation (when to flag CRITICAL, etc.)
5. **Output** — Expected structure (severity, recommendations, activation_level)

### Example: Create a New Skill

```yaml
name: performance_hotspots          # 1. Name
version: 1.0
description:  "Identify performance-critical modules and bottlenecks"  # 2. Purpose

uses:                               # 3. Stones
  - stone: hotspots
  - stone: choke_points
  - stone: gravity

interpretation:                     # 4. Rules
  rules:
    - if: choke_points_count > 3
      then: severity = WARNING
      recommendation: "Review bottlenecks for optimization"

agent_context:
  when_to_invoke: "Performance analysis workflows"
  estimated_tokens: "250-600"
```

---

## Skill Registry

### Built-in Skills (v1.0)

#### 1. `architecture_summary`
- **Purpose**: Quick overview (entry point)
- **Scope**: Doctor + domains + entropy
- **Output**: Top 3 insights + activation_level
- **Tokens**: ~100-300
- **Use when**: "What's this codebase like?"

#### 2. `architecture_investigate`
- **Purpose**: Full health check
- **Scope**: Doctor + gravity + hotspots + cycles + interpretation
- **Output**: Severity + recommendations + findings
- **Tokens**: ~300-800
- **Use when**: "Full analysis" or activation_level is hot

#### 3. `architecture_review`
- **Purpose**: PR impact assessment
- **Scope**: Impact + doctor + drift
- **Output**: Risk level + blast radius + approval criteria
- **Tokens**: ~200-600
- **Use when**: Pre-merge review workflow

---

## Extending Skills

### Non-Breaking Extensions (v1.1+)

Possible future additions:
- [ ] New skills (add files to `.kit/skills/`)
- [ ] New stone compositions (modify `uses:` list)
- [ ] New interpretation rules (`rules:` section)
- [ ] Conditional stone execution
- [ ] Parameterized stone arguments

### NEVER (Would Break v1.0)

- ❌ Change skill names
- ❌ Remove skills
- ❌ Change output schema structure
- ❌ Add Turing-complete logic
- ❌ Require Python execution

---

## Troubleshooting

### "Skill not found"
```
Error: Skill not found: my_skill
Available skills: [architecture_summary, architecture_investigate, ...]
```

**Solution**: Check skill filename matches skill name in YAML.
Filename: `my_skill.yaml`
Content: `name: my_skill`

### "Invalid skill YAML"
- Skills use `kit_skills_list` → skips malformed files silently
- Validate with: `python -c "import yaml; yaml.safe_load(open('.kit/skills/my_skill.yaml'))"`

### "Stones not executing"
- Check stone names match `kit stones` output
- Verify workspace root is set correctly
- Run `kit query <stone_name>` manually to debug

---

## Token Cost Estimates

| Skill | Cost | When to Use |
|-------|------|------------|
| architecture_summary | 100-300 | Entry point, quick overview |
| architecture_investigate | 300-800 | Full analysis, deep dive |
| architecture_review | 200-600 | PR workflows, merge assessment |

**Savings vs. manual composition**: ~30-50% reduction by avoiding duplicate stone execution.

---

## Agent Integration Examples

### Claude Cowork Mode
```
User: "Investigate this repo's architecture"
Claude: calls kit_skill_run(architecture_investigate)
Result: Session update with findings → committed to layer2_core/
```

### Gemini Agent
```
User: "Is this safe to merge?"
Gemini: calls kit_skill_run(architecture_review)
      analyzes blast_radius + hotspots_touched
Result: Approve/Request review decision
```

### Custom Orchestrator
```python
from kit_mcp_server import MCPServer

server = MCPServer()

# Discover skills
skills = server.handle_kit_skills_list()

# Run skill
result = server.handle_kit_skill_run(
    skill_name="architecture_investigate",
    inputs={"depth": "thorough"}
)

# Use result
if result["severity"] == "CRITICAL":
    escalate_to_architect(result["recommendations"])
```

---

## FAQ

**Q: Can agents modify skills?**  
A: No. Skills are read-only definitions in `.kit/skills/`. Agents discover and invoke them.

**Q: What if I want custom logic?**  
A: Use `interpretation/rules` (if-then clauses in YAML). For complex logic, use external orchestration.

**Q: Can skills call other skills?**  
A: Not yet. MCP tool composition happens at agent level.

**Q: How do I test a skill?**  
A: `python -c "from kit_mcp_server import MCPServer; s = MCPServer(); print(s.handle_kit_skill_run('skill_name'))"`

**Q: Are skills versioned?**  
A: Yes. Each skill has `version: X.Y`. Breaking changes increment major version.

---

## See Also

- **[SPEC.md](SPEC.md)** — Complete skill definition specification
- **[AGENT_CONTEXT.md](../AGENT_CONTEXT.md)** — Agent quick reference (skills section)
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** — System architecture overview
