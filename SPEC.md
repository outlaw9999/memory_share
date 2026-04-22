# Execution Physics Spec v1.2.4

> v1.2.4 is already correct at runtime — now we are only writing down why it is correct.

---

## Invariants (Laws of Execution)

| # | Invariant | Enforcement Layer |
|---|----------|-------------------|
| I1 | Memory must have canonical representation | MemoryRouter canonicalization |
| I2 | Uncommitted state must not persist to disk | seal guard (MemoryRouter) |
| I3 | Graph edges must have deterministic source | Vantage (structural sensor) |
| I4 | No orphan nodes in dependency graph | Vantage (orphan detection) |
| I5 | Observation must have valid structural_hash | schema factory (write-time) |
| I6 | State must have commit lineage | memory topology (commit chain) |
| I7 | Access must respect layer hierarchy | memory_scoring (layer decay) |
| I8 | Decisions must be tagged | command_registry (tag validation) |

---

## Layer Mapping

```
┌─────────────────────────────────────────────────────┐
│ KIT CLI (Intent)                                     │
│   → kit learn / kit recall / kit doctor              │
├─────────────────────────────────────────────────────┤
│ MEMORYROUTER (Policy + Routing)                     │
│   → seal guard (I2)                               │
│   → canonicalization (I1)                          │
│   → routing decisions                            │
├────────────────────────────────----------------------─┤
│ SAMBRAIN (Orchestration)                          │
│   → execution flow                              │
│   → context compilation                        │
├─────────────────────────────────────────────────────┤
│ VANTAGE (Structural Truth)                        │
│   → graph integrity (I3)                         │
│   → orphan detection (I4)                       │
│   → hash validation (I5)                        │
├─────────────────────────────────────────────────────┤
│ SQLITE (State Persistence)                       │
│   → observations table                         │
│   → structure_edges table                      │
│   → commit chain (I6)                          │
└─────────────────────────────────────────────────────┘
```

---

## Execution Flow Constraints

### Valid Transitions

| From | Via | To |
|-----|-----|-----|
| working | commit | episodic |
| episodic | bake | semantic |
| semantic | archive | frozen |

### Invalid Transitions (Enforced)

- working → frozen (must pass through semantic)
- uncommitted → persisted (seal guard blocks)
- orphaned → queryable (Vantage blocks)

---

## Sealing Boundary

```
UNCOMMITTED (working memory)
       ↓ seal guard (I2)
COMMITTED (episodic layer)
       ↓ bake (I5, I6)
BAKED (semantic layer)
       ↓ archive
FROZEN (immutable)
```

---

## Graph Integrity Rules

### Edge Validity

- IMPORTS: source must import target
- INHERITS: source must extend target
- CALLS: source must call target (runtime reference)

### Confidence Scoring

| Edge Type | Default Confidence |
|----------|-------------------|
| IMPORTS | 1.0 |
| INHERITS | 1.0 |
| CALLS | 0.7 (requires resolution) |

---

## Quick Reference

| Command | Layer | Invariant |
|---------|-------|----------|
| kit learn | MemoryRouter | I1, I2, I8 |
| kit recall | SAMBrain | I1, I7 |
| kit doctor | Vantage | I3, I4, I5 |
| kit commit | MemoryRouter | I2, I6 |
| kit bake | Vantage | I5, I6 |

---

## Non-Goals (Explicit)

- NOT a programming language spec
- NOT an API contract (use --help for that)
- NOT a migration guide (see MIGRATION.md)
- NOT a test suite