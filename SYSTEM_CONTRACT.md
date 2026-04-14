# System Contract v1.0 (Runtime Spine Contract)

> **Effective**: v1.2.4
> **Purpose**: Define single source of truth for execution authority.

---

## 1. State Model

```
Memory State = {Ephemeral, Repo, Global}

Truth Source (priority order):
  1. Ephemeral: In-memory buffer (kit_vantage.py outputs)
  2. Repo: .kit/brain.db (local SQLite)
  3. Global: ~/.kit/brain.db (optional, attached)
```

### Write Rule
- `learn()` → ALWAYS writes to **Repo** (local SQLite first)
- `learn(..., to_global=True)` → writes to **Global** if attached

### Read Rule
- `search()` → reads from Repo + Global (hybrid)
- `recall()` → reads from Repo + Global with scope filtering

---

## 2. Execution Authority (Priority Order)

```
Final Authority = [
  1. L3 Registry (INVARIANT rules)        -- HARD BLOCK
  2. kit_decision (decide())             -- Signals from analysis
  3. kit_governance (run_preflight)       -- Commit-time enforcement
  4. SAMBrain (runtime scoring)          -- Retrieval ranking
]
```

### Conflict Resolution
- L3 MANDATORY + INVARIANT tag → **BLOCK** unconditionally
- L3 RECOMMENDED + DECISION tag → **WARN** (allow commit)
- risk_engine signal = "high" → **BLOCK**
- risk_engine signal = "medium/low" → **WARN**

---

## 3. Execution Flow

```
CLI input (kit learn)
    ↓
[1] Input Validation (kit_invariants)
    ↓
[2] Tag Normalization (validate: invariant|decision|preference|note|friction)
    ↓
[3] L3 MANDATORY Check → FAIL → ABORT
    ↓
[4] SAMBrain.learn() → write to SQLite
    ↓
[5] Increment version (cognition_version)
```

---

## 4. Failure Rules

| Scenario | Action |
|----------|--------|
| L3 MANDATORY violation detected | BLOCK immediately, do not write |
| Risk signal = "high" | BLOCK at commit-time |
| SQLite lock timeout | FAIL-FAST (raise exception, no retry loop) |
| Memory Router conflict | Use SAMBrain as truth source |

---

## 5. Invariant Enforced

```python
# These rules are ALWAYS enforced at runtime:
INVARIANTS = [
    "L3-SQL-001": "Parameterized Query Requirement",
    "L3-AUTH-001": "Explicit Authentication Guard", 
    "L3-MEM-001": "Workspace-Scoped Memory",
    "L3-ENC-001": "UTF-8 Input Normalization",
]
```

---

## 6. Boundaries (Where NOT to write)

```
DO NOT write to:
- AGENTS.md (auto-modified stopped in v1.2.3)
- .git/hooks/ (external)
- IDE workspace files (external)
- Remote (unless to_global=True and explicit)
```

---

## 7. Version Contract

```
SAMBrain.cognition_version = INTEGER
  - Incremented on EVERY learn() success
  - Used as event marker for stream_events()
  - NOT a semantic version

Current version: v1.2.3.x
Next contract version: v1.2.4 (Runtime Spine)
```

---

## 8. Authority Summary

| Operation | Authority | Output |
|-----------|-----------|--------|
| `learn()` | SAMBrain | fact_id |
| `search()` | SAMBrain | list[Memory] |
| `recall()` | SAMBrain | list[Memory] |
| `decide()` | kit_decision | Action{BLOCK,WARN,PASS} |
| `govern()` | kit_governance | PreflightResult |
| `validate()` | L3 Registry | compliance report |

---

## 9. Non-Goals (Explicit)

- RuntimeSpine: Not built yet (contract defines it)
- EnvRouter: Not a priority module
- L3 Enforcement Bridge: TODO in v1.2.4

---

## 10. Contract Version

- **Version**: 1.0
- **Effective From**: v1.2.4
- **Contract Owner**: SAMBrain as single execution entry

---

# Execution Path Diagram

```
kit cli/main.py
    ↓
api.learn()
    ↓
SAMBrain.learn()                      ← PRIMARY ENTRY
    ↓
[INVARIANTS ENFORCED]
    ├─ sanitize_global_metadata()
    └─ enforce_no_global_contamination()
    ↓
[WRITE TO SQLite]
    ├─ BEGIN IMMEDIATE
    ├─ Upsert node
    ├─ Insert observation
    ├─ Increment version
    └─ COMMIT
    ↓
RETURN fact_id
```

---

# End Contract v1.0