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

## Token Cost Comparison

**Old way** (reading docs):
```
AGENT_CONTEXT.md
docs/METRICS.md
docs/ARCHITECTURE.md
docs/LIMITATIONS.md
Total: 10,000—30,000 tokens
```

**New way** (CLI):
```
kit stones          → 500 tokens (list all stones)
kit stone gravity   → 150 tokens (specific stone)
Total: 50—200 tokens (100x reduction)
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

## How Agents Should Use .kit

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
