# .kit Master Architecture Diagram

> **Philosophy**: LLM plans. `.kit` analyzes. Agents orchestrate.

---

## 8-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       AGENTS (LLM)                          │
│                   (Orchestrators Only)                      │
└────────────────────────┬──────────────────────────────────┘
                         │
                    Tool Calls
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 7: Broker (Orchestration Layer)                    │
│  ├─ Deduplication                                         │
│  ├─ Request Queue                                         │
│  ├─ Result Cache (TTL)                                    │
│  └─ Execution Budget                                      │
└────────────────────────┬──────────────────────────────────┘
                         │
                    MCP Dispatch
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 6: Decision Engine (Policy Layer)                  │
│  ├─ Deterministic Rules                                   │
│  ├─ Severity Evaluation                                   │
│  └─ Action Plan Generation                                │
└────────────────────────┬──────────────────────────────────┘
                         │
                    Skill Execution
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 5: Skills Framework (Workflow Layer)               │
│  ├─ architecture_summary                                  │
│  ├─ architecture_investigate                              │
│  └─ architecture_review                                   │
└────────────────────────┬──────────────────────────────────┘
                         │
                    Stone Composition
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 4: Diagnostic Stones (Metric Layer)                │
│  ├─ cycles (detect circular deps)                         │
│  ├─ gravity (module importance)                           │
│  ├─ entropy (coupling measure)                            │
│  ├─ hotspots (change frequency)                           │
│  ├─ dead_code (unreachable symbols)                       │
│  └─ impact (blast radius)                                 │
└────────────────────────┬──────────────────────────────────┘
                         │
                    SQL Queries
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 3: Graph Engine (Store Layer)                      │
│  ├─ SQLite (Symbols, Calls, Modules)                      │
│  ├─ Indexed Lookups                                       │
│  └─ Dependency Graph                                      │
└────────────────────────┬──────────────────────────────────┘
                         │
                    Symbol Resolution
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 2: Atlas Indexer (Parse Layer)                     │
│  ├─ AST Parsing                                           │
│  ├─ Symbol Identity                                       │
│  └─ Scope Analysis                                        │
└────────────────────────┬──────────────────────────────────┘
                         │
                    Source Code
                         │
┌────────────────────────▼──────────────────────────────────┐
│  Layer 1: Codebase (Data Layer)                           │
│  ├─ Python / TypeScript / Go / Rust...                    │
│  └─ [Read-Only]                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Control Plane vs Data Plane

```
                    CONTROL PLANE
    (Orchestration, Policy, Decisions)

┌──────────────────────────────────────────┐
│  Agents (Planning)                       │
│           ↓                              │
│  Broker (Queueing)                       │
│           ↓                              │
│  Decision Engine (Rules)                 │
│           ↓                              │
│  Skills (Workflows)                      │
└──────────────────────────────────────────┘
           │
           │ (triggers)
           ↓

    DATA PLANE
(Analysis, Metrics, Facts)

┌──────────────────────────────────────────┐
│  Stones (Queries)                        │
│           ↓                              │
│  Graph Engine (Index)                    │
│           ↓                              │
│  Atlas Indexer (Parse)                   │
│           ↓                              │
│  Codebase (Source)                       │
└──────────────────────────────────────────┘
```

---

## Data Flow Example: Agent asks "Is AuthService too big?"

```
┌─ Agent ─────────────────────────────────────────────┐
│  Question: "Is AuthService too big?"                │
└─────────────────────────┬──────────────────────────┘

↓

┌─ Broker ────────────────────────────────────────────┐
│  1. Check cache: skill:architecture_investigate    │
│  2. If exist + fresh → return                      │
│  3. Else → queue request                           │
└─────────────────────────┬──────────────────────────┘

↓

┌─ Decision Engine ───────────────────────────────────┐
│  Pre-evaluate: Will I need impact analysis?         │
│  Decide: Run skill_investigate                      │
└─────────────────────────┬──────────────────────────┘

↓

┌─ Skills ────────────────────────────────────────────┐
│  Execute: architecture_investigate                  │
│  Compose: gravity + hotspots + cycles               │
└─────────────────────────┬──────────────────────────┘

↓

┌─ Stones ────────────────────────────────────────────┐
│  query("gravity WHERE module = 'AuthService'")      │
│  query("hotspots WHERE module = 'AuthService'")     │
│  query("cycles WHERE involve = 'AuthService'")      │
└─────────────────────────┬──────────────────────────┘

↓

┌─ Graph Engine ──────────────────────────────────────┐
│  SELECT calls FROM graph WHERE from = 'AuthService'│
│  GROUP BY to                                        │
│  ORDER BY count DESC                                │
└─────────────────────────┬──────────────────────────┘

↓

┌─ Codebase ──────────────────────────────────────────┐
│  AuthService.py (450 lines)                         │
│  (Indexed, not re-parsed)                           │
└─────────────────────────┬──────────────────────────┘

↓ (results bubble back up)

┌─ Agent receives signal ─────────────────────────────┐
│                                                     │
│  {                                                  │
│    "severity": "WARNING",                          │
│    "issues": ["high_gravity"],                     │
│    "top_symbol": "AuthService",                    │
│    "next_actions": [                               │
│      "run_impact"                                  │
│    ],                                              │
│    "payload_ref": "skill:investigate:abc123"       │
│  }                                                  │
│                                                     │
│  Agent: "Should split AuthService"                 │
└─────────────────────────────────────────────────────┘
```

---

## Token Flow at Each Layer

```
Layer 8: Agent prompt
   ↓
   tokens: ~100 (signal)

Layer 7: Broker
   ↓
   tokens: ~0 (cache hit)

Layer 6: Decision Engine
   ↓
   tokens: ~50 (policy output)

Layer 5: Skills
   ↓
   tokens: ~100 (skill instructions)

Layer 4: Stones
   ↓
   tokens: ~500 (raw metrics)

Layer 3: Graph
   (no token cost)

Layer 2: Atlas
   (no token cost)

Layer 1: Codebase
   ✅ NOT SENT TO LLM

TOTAL: ~750 tokens
SAVED: ~49,250 tokens (vs reading code directly)
```

---

## Multi-Agent Behavior Without Broker

```
Agent A → kit_skill_run(investigate)
Agent B → kit_skill_run(investigate)        ← WASTED COMPUTATION
Agent C → kit_skill_run(investigate)        ← WASTED COMPUTATION
Agent D → kit_query_stone(gravity)          ← RACE CONDITION

Result: CPU spike, cache miss, memory explosion
```

---

## Multi-Agent Behavior With Broker

```
Agent A → ┐
Agent B → ├─ Broker ─ dedup/cache ─ kit_skill_run(investigate) [once]
Agent C → ┤                              ↓
Agent D → └─ queue                      Graph Engine

All agents get result in ~100ms
No redundant computation
Cache hit for next 15 seconds
```

---

## Maturity Levels

| Level | Name                      | Status | `.kit` |
|-------|---------------------------|--------|--------|
| L1    | Raw Code to LLM           | ❌     | N/A    |
| L2    | Prompts + Tools           | ❌     | N/A    |
| L3    | Structured Analysis       | ✅     | Here   |
| L4    | Skill Abstraction         | ✅     | Here   |
| L5    | Deterministic Rules       | ✅     | Here   |
| L6    | Signal Compression        | ✅     | Here   |
| L7    | Multi-Agent Orchestration | ✅     | Here   |
| L8    | Continuous Watchdog       | ⏳     | Next   |

`.kit` is **Level 7/8 Ready**.

---

## Comparison with Production Systems

| System           | Architecture | Pattern       | Mode |
|------------------|--------------|---------------|------|
| Cursor           | 7 layers     | Broker + LLM  | Sync |
| Devin            | 8 layers     | Planning + action | Async |
| Sourcegraph Cody | 6 layers     | Search + LLM  | Sync |
| **`.kit`**       | **7 layers** | **Broker + Skills** | **Sync** |

`.kit` occupies unique position: **Architecture Coprocessor**.

---

## Philosophy

```
❌ LLM analyzes codebase
   (expensive, slow, hallucination risk)

✅ Tool analyzes codebase
   LLM orchestrates tool calls
   (cheap, fast, deterministic)
```

---

## Implementation Status

### Tier 1: Foundation ✅
- [x] Atlas Indexer (Layer 2)
- [x] Graph Engine (Layer 3)
- [x] Diagnostic Stones (Layer 4)

### Tier 2: Abstraction ✅
- [x] Skills Framework (Layer 5)
- [x] Decision Engine (Layer 6)
- [x] Signal Envelope + Reasoning Hints (Layer 7a)
- [x] ToolBroker (Layer 7b)

### Tier 3: Autonomy ⏳
- [ ] Architecture Watchdog (Layer 8)
- [ ] Continuous CI/CD Integration
- [ ] Automated PR Comments

### Future Enhancements
- [ ] Custom Policies (YAML)
- [ ] Skill Composition (skills calling skills)
- [ ] Streaming Results
- [ ] Distributed Broker

---

## Key Insight

`.kit` achieves **production scalability** not by making LLM smarter, but by:

1. **Removing LLM from analysis** (Graph Engine does it)
2. **Removing LLM from reasoning** (Decision Engine does it)
3. **Compressing output** (Signal Envelope does it)
4. **Deduplicating calls** (Broker does it)

This is why `.kit` works with 10M+ LOC without breaking a sweat.

---

## Next Phase: Architecture Watchdog

See `ARCHITECTURE_WATCHDOG.md` for continuous monitoring design.

```
Code Change → .kit Auto-Analysis → Decision Engine → PR Alert
```

This makes `.kit` **continuously monitor** architecture health.
