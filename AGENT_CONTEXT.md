# AGENT_CONTEXT.md — AI Tool Quick Reference

**For**: Copilot, Gemini, Claude, and other AI coding assistants  
**Purpose**: Bootstrap understanding of `.kit` system in < 2 minutes

---

## 🚀 Start Here: Self-Describing CLI

Don't read this file. Use the CLI instead:

```bash
# Discover all stones (14 total)
kit stones

# Learn about a specific stone
kit stone gravity
kit stone utility_hubs
kit stone graph_health
```

**Output is JSON** — parse this, don't read markdown.

---

## 🎯 NEW: MCP Server Interface (Recommended for AI Agents)

**PREFERRED METHOD**: Use MCP server for ~100x token efficiency.

### Quick Setup for Claude/Gemini/etc.

**Client config (environment variable or client settings):**
```
KIT_MCP_SERVER=stdio:///path/to/kit_mcp_server.py
```

Or direct Python:
```python
import subprocess
mcp_server = subprocess.Popen(
    ["python", "kit_mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)
```

### Available MCP Tools (6 core + 2 skill tools)

| Tool | Purpose | Cost |
|------|---------|------|
| `kit_doctor` | Health check (5 metrics + recommendations) | ~100 tokens |
| `kit_query_stone` | Execute diagnostic stone | varies |
| `kit_stones_list` | Discover all stones + metadata | ~50 tokens |
| `kit_symbol_search` | Code search (unified code + docs) | ~100 tokens |
| `kit_impact` | Blast radius analysis (reverse call graph) | ~150 tokens |
| `kit_context` | Symbol context (definition + callers + callees) | ~100 tokens |
| **`kit_skills_list`** | **Discover available skills** | **~50 tokens** |
| **`kit_skill_run`** | **Execute a high-level skill (multi-stone workflow)** | **~200-800 tokens** |

### Example: MCP Call

Agent calls MCP with:
```json
{
  "method": "tools/call",
  "params": {
    "name": "kit_doctor",
    "arguments": {"format": "json"}
  }
}
```

Response (~100 tokens total):
```json
{
  "status": "success",
  "result": {
    "overall_status": "HEALTHY",
    "cycles_detected": 0,
    "critical_gravity_nodes": 0,
    "graph_confidence": "HIGH",
    "recommendations": "..."
  }
}
```

**Token cost**: ~100 tokens (vs. 50,000 if agent read codebase)

---

## 🎓 NEW: Skills Framework (Agent-Oriented Workflows)

**What Are Skills?**

Skills are **high-level diagnostic workflows** that compose multiple stones into reusable patterns. Instead of calling individual stones step-by-step, agents invoke a skill once with a intent.

### Example: Run Full Architecture Investigation

**Before (manual composition):**
```
1. kit_doctor → check overall health
2. kit_query_stone (gravity) → check dependencies
3. kit_query_stone (hotspots) → find risky modules
4. kit_query_stone (cycles) → detect deadlocks
5. Interpret results → synthesize findings
```

**After (skill):**
```
kit_skill_run skill_name=architecture_investigate
```

Boom. One call. Same insights. ~50% fewer tokens.

### Discover Skills (50 tokens)

Agent calls:
```json
{
  "name": "kit_skills_list",
  "arguments": {}
}
```

Response:
```json
{
  "skills": [
    {
      "name": "architecture_summary",
      "version": "1.0",
      "description": "Quick high-level architecture overview",
      "tags": ["summary", "entry-point"],
      "estimated_tokens": "100-300"
    },
    {
      "name": "architecture_investigate",
      "version": "1.0",
      "description": "Full architecture health check with insights",
      "tags": ["health", "agent-primary"],
      "estimated_tokens": "300-800"
    },
    {
      "name": "architecture_review",
      "version": "1.0",
      "description": "Pre-merge architectural impact assessment",
      "tags": ["review", "pr"],
      "estimated_tokens": "200-600"
    }
  ]
}
```

### Run a Skill (200-800 tokens depending on skill)

Agent calls:
```json
{
  "name": "kit_skill_run",
  "arguments": {
    "skill_name": "architecture_investigate",
    "inputs": {
      "depth": "quick"
    }
  }
}
```

Response:
```json
{
  "status": "success",
  "skill": "architecture_investigate",
  "severity": "HEALTHY",
  "activation_level": "cold",
  "recommendations": [
    "Architecture is in good shape; focus on maintenance"
  ],
  "results": {
    "doctor": {...},
    "gravity": {...},
    "hotspots": {...},
    "cycles": {...}
  }
}
```

### When to Use Skills

| Situation | Tool | Reason |
|-----------|------|--------|
| "What's this codebase like?" | `kit_skill_run`<br/>(architecture_summary) | Quick overview, entry point |
| "Full health check" | `kit_skill_run`<br/>(architecture_investigate) | Multi-stone analysis, actionable |
| "PR impact?" | `kit_skill_run`<br/>(architecture_review) | Risk assessment for merge |
| "Tell me about gravity" | `kit_query_stone`<br/>(gravity) | Single metric, detailed |
| "Find symbol X" | `kit_symbol_search` | Code navigation |
| "Who calls this?" | `kit_impact` or `kit_context` | Dependency exploration |

**Rule of thumb**: Use skills for **workflows**, stones for **single metrics**.

---

## Token Cost Comparison

| Method | Cost | When to Use |
|--------|------|------------|
| **MCP server** (NEW) | ~100 tokens | ✅ Preferred for all AI agents |
| CLI subprocess calls | ~200-500 tokens | Fallback if MCP unavailable |
| Reading docs/code | 10,000-200,000 tokens | ❌ Avoid - inefficient |

**Example savings:**
```
Without MCP:  50,000+ tokens for analysis
With MCP:     ~100 tokens for same analysis
Ratio:        500× reduction
```

---

## What is .kit?

A **local semantic code graph engine** for analyzing repository structure. Generates intelligence without cloud services.

### System Stack

```
Repository Code
    ↓
[Atlas] Indexer → SQLite graph (symbols, calls)
    ↓
[11 Diagnostic Stones] SQL queries → metrics
    ↓
[Doctor] Orchestrator → health report
    ↓
CLI Output → Agents, tools, reports
```

**No external dependencies. Fully offline.**

---

## Discovery: How Agents Learn the System

### Step 1: List All Stones (50 tokens)

```bash
kit stones
```

Output:
```json
{
  "primitives": [
    {"name": "cycles", "purpose": "Detect circular dependencies", "confidence": "HIGH"},
    ...
  ],
  "advanced": [...],
  "orchestrators": [...],
  "total": 14,
  "note": "Run 'kit stone <name>' for full details"
}
```

### Step 2: Learn a Specific Stone (150 tokens each)

```bash
kit stone gravity
```

Output:
```json
{
  "name": "gravity",
  "category": "primitive",
  "purpose": "Detect dependency concentration",
  "detects": "Nodes with high centrality",
  "risk": "MEDIUM - biased by utility hubs",
  "mitigation": "Cross-check with utility_hubs stone",
  "confidence": "MEDIUM",
  "query_command": "kit query gravity --timeout 30"
}
```

Agent now knows:
- What gravity detects ✓
- Why it might be wrong (utility hubs bias) ✓
- How to run it ✓
- What to do with results (cross-check) ✓

### Step 3: Run a Stone (hundreds of tokens for results only)

```bash
kit query gravity
```

---

## The 11 Diagnostic Stones (Complete Spellbook)

**For detailed stone info, use the CLI:**
```bash
kit stones       # List all stones
kit stone <name> # Get details on any stone
```

**Example**: To understand what `utility_hubs` does without reading this file:
```bash
kit stone utility_hubs
```

Agents don't memorize stones. They query the CLI and parse JSON.

---

## MCP Agent Patterns

### Pattern: Health Check (10 tokens)

```python
# Minimal pattern - get architecture health in one call
health = mcp_call("kit_doctor", {})
if health.overall_status == "HEALTHY":
    proceed_with_refactor()
else:
    analyze_with_stones()
```

### Pattern: Diagnostic Deep Dive (100 tokens)

```python
# Get diagnostics + discover available metrics
health = mcp_call("kit_doctor", {})
stones = mcp_call("kit_stones_list", {})

# Pick a stone for deeper analysis
if health.cycles_detected > 0:
    cycles_detail = mcp_call("kit_query_stone", {
        "stone_name": "cycles",
        "format": "json"
    })
    for cycle in cycles_detail.cycles:
        impact = mcp_call("kit_impact", {
            "symbol": cycle["node"],
            "depth": 3,
            "limit": 20
        })
        print(f"Cycle {cycle} affects {len(impact)} symbols")
```

### Pattern: Code Safety Analysis (150 tokens)

```python
# Before refactoring a symbol, understand blast radius
def analyze_symbol_safety(symbol_name: str):
    context = mcp_call("kit_context", {
        "symbol": symbol_name,
        "callers_limit": 10,
        "callees_limit": 10
    })
    
    impact = mcp_call("kit_impact", {
        "symbol": symbol_name,
        "depth": 4,
        "limit": 50
    })
    
    return {
        "definition": context.definition,
        "affected_count": len(impact.affected),
        "max_depth": impact.metrics.max_depth,
        "safe_to_modify": len(impact.affected) < 10
    }
```

---

## How Agents Should Use .kit

### Recommended: Use MCP Server

Replace all CLI calls with MCP tool calls:

```python
# ❌ Old (shell subprocess - inefficient)
result = subprocess.run(["python", "bin/kit", "doctor"], capture_output=True)

# ✅ New (MCP - efficient)
result = mcp_call("kit_doctor", {})
```

**Agents that support MCP**:
- Claude (via stdio)
- Gemini (via tools)
- Custom Python agents
- Cursor / Aider

---

## Fallback: CLI Interface

If MCP is unavailable, use CLI directly (but less efficient):

### Pattern #1: Discover, Query, Parse

```bash
# Step 1: Discover what stones are available (once per session)
kit stones | parse_json()

# Step 2: Learn about a specific stone if unsure
kit stone hotspots | parse_json()

# Step 3: Run the stone and parse results
kit query hotspots --timeout 30 | parse_json()

# Step 4: Interpret results based on metadata
if result.risk == "HIGH":
    take_action(result)
```

### Pattern #2: Risk Assessment

```python
# Agent algorithm: Assess code quality risk
def assess_risk():
    doctor_report = run_cli("kit doctor")
    
    if doctor_report.graph_confidence < 0.7:
        return "UNCERTAIN - incomplete graph"
    
    risk_score = 0
    if doctor_report.cycles > 0:
        risk_score += 10
    if len(doctor_report.hotspots) > 2:
        risk_score += 5
    
    return "HIGH" if risk_score > 10 else "MEDIUM" if risk_score > 5 else "LOW"
```

### Pattern #3: Architecture Governance

```python
# Check for architecture violations
violations = run_cli("kit query architecture")
if violations:
    print(f"⚠️ {len(violations)} layer violations found")
    for v in violations:
        impact = run_cli(f"kit query impact --symbol {v.symbol}")
        print(f"  {v.symbol}: affects {len(impact)} symbols")
```

---

## CLI Reference (All Commands)

**Agents ONLY need these 5 commands:**

```bash
# 1. Discover stones (50 tokens)
kit stones

# 2. Learn about a stone (150 tokens per stone)
kit stone <name>

# 3. Run a stone (hundreds of tokens for results)
kit query <stone> [--timeout N]

# 4. Full health check (orchestrator)
kit doctor [--timeout N]

# 5. Symbol search (if needed)
kit symbol <query>
```

**All output is JSON** — parse, don't read.

---

## Limitations (Brief, Read First)

Agent workflow should check limitations immediately:

```bash
# Learn limitations from CLI metadata
kit stone graph_health   # Check what risks it warns about
kit queryave utility_hubs # See what mitigation is recommended

# For full details (humans only):
https://github.com/outlaw9999/memory_share/blob/main/docs/LIMITATIONS.md
```

**Key ones**:
- **Edge Incompleteness**: Graph may be 20-40% incomplete (static analysis limit)
  - Check `graph_confidence` — if < 0.7, verify with code review
- **Utility Gravity Well**: High fan-out utilities appear more central than they are
  - Mitigation: Always cross-check `gravity` with `utility_hubs`
- **Cycle Depth Limit**: Only detects cycles < 6 hops
  - Acceptable: 90% of real cycles are < 3 hops

---

## Architecture Stability (v1.0)

**Frozen interface** — safe for production:
- ✓ CLI commands stable (kit, init, index, query, doctor, stones, stone)
- ✓ Output format locked (JSON)
- ✓ Database schema immutable
- ✓ Stone list (11 + 2 orchestrators) unchanging in v1.x

**Breaking changes only in v2.0** (multi-language support).

---

## What Makes .kit Different

✅ **CLI describes itself** — agents don't read markdown  
✅ **Metadata in JSON** — stone purposes, risks, mitigations in output  
✅ **Modular stones** — 14 independent queries, not monolithic  
✅ **100x token savings** — CLI queries (50-200 tokens) vs reading docs (10-30k tokens)  
✅ **Frozen v1.0** — API stable for app integration  

**Philosophy**: Self-describing CLI > documentation. Agents query tools, don't read guides.

---

## Start Using .kit Now

**Agent entry point**:
```bash
kit stones  # Discover what's available (JSON is the documentation)
```

**Then**:
```bash
kit doctor  # Full health report
```

**That's it.** Agents don't memorize. They run commands and parse output.

---

**For humans only**: [docs/LIMITATIONS.md](docs/LIMITATIONS.md) and [README.md](README.md)
