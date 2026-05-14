# KIT System Specifications

This document consolidates the core specifications of the KIT system, including the cognitive substrate architecture, containment guarantees, and execution physics.

---

## 1. ARCHITECTURE: Final Cognitive Substrate Architecture v2

### Three Concerns, One Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PLANE 1: INTERACTION SURFACE (Git is UI, Stateless, No Cognition)     │
│                                                                         │
│   git commit / merge / rebase                                           │
│        │                                                                 │
│        ▼                                                                 │
│   Git Hooks (thin sensors, never parse/filter/decide)                   │
│        │                                                                 │
│        ▼                                                                 │
│   RawGitEvent JSON  →  stdout                                           │
│└─────────────────────────────────────────────────────────────────────────┘
        │  stdin
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PLANE 2: COGNITIVE SUBSTRATE (Event-driven, No CLI, Only Intent)      │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │                   PRE-FLOW (read-only)                      │      │
│   │  RawGitEvent → Intent Normalizer → Planner → ExecutionPlan  │      │
│   └─────────────────────────────────────────────────────────────┘      │
│        │                                                                │
│        ▼                                                                │
│   ┌────────────┐    ┌────────────────────────────────────────────┐     │
│   │ PolicyGuard│    │       AUTHORITIES (3 concerns)             │     │
│   │ (single    │───▶│                                            │     │
│   │  check)    │    │  Truth Gate:  kit-vantage (certify reality)│     │
│   │            │    │  Safety Gate: PolicyGuard (govern traffic) │     │
│   │ depth      │    │  State Sink:  MemoryRouter (project memory)│     │
│   │ storm      │    └────────────────────────────────────────────┘     │
│   │ fingerprint│              │                │                       │
│   └────────────┘              ▼                ▼                       │
│         │             ┌──────────────┐  ┌──────────────┐              │
│         ▼             │ Epistemic    │  │ MemoryRouter  │              │
│   ┌──────────┐        │  Engine      │  │ (write only)  │              │
│   │ Executor │        │  (verdict)   │  │              │              │
│   │(gate)    │        └──────────────┘  └──────────────┘              │
│   └──────────┘              │                  ▲                       │
│         │                   │                  │                       │
│         └────── single gate ──── approved traces only                  │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │              EXECUTION (single gate)                        │      │
│   │  RuntimeExecutor._execute_step()  →  side-effect dispatch   │      │
│   └─────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DIAGNOSTIC ZONE (CLI, debug, repair — read-only, isolated)           │
│  Not part of cognitive loop. Never emits events into Plane 2.         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Authority Boundaries

| Authority      | Component          | Power                          | Forbidden                     |
|----------------|--------------------|--------------------------------|-------------------------------|
| Truth Gate     | kit-vantage        | Certify reality                | Memory decisions, governance  |
| Safety Gate    | PolicyGuard        | Govern traffic                 | Epistemic checks              |
| State Sink     | MemoryRouter       | Single write path              | Self-authoring, truth eval    |

### Invariants (Locked)

1. **`kit-vantage` does not approve memory. It only certifies reality.**
2. **PolicyGuard does not evaluate truth. It only governs traffic.**
3. **MemoryRouter does not evaluate truth or safety. It only projects.**
4. Memory is a deterministic consequence of truth, not a source of truth.
5. No reverse flow from Plane 2 to Plane 1.
6. Runtime never mutates during planning.
7. Single execution gate for all side effects.
8. **Cognition may be probabilistic. Reality transitions must be deterministic.**
9. Git anchors reality but does not define truth.
10. Hallucination is contained, not prevented.

---

## 2. CONTAINMENT: Verifiable Epistemic Spec v1.0

### Core Thesis

> Kit does not prevent hallucination.
> Kit prevents hallucination from becoming reality.

### Three Domains

```
┌─────────────────────────────────────────────────────────────────────┐
│  UNBOUNDED DOMAIN (probabilistic, no structural guarantee)         │
│  LLM cognition, agent reasoning, semantic inference                │
│  RULE: May produce any output. No constraint on truth.             │
├─────────────────────────────────────────────────────────────────────┤
│  ⇓ event (RawGitEvent / Intent signal)                             │
├─────────────────────────────────────────────────────────────────────┤
│  BOUNDED DOMAIN (structured, deterministic pipeline)               │
│  Intent → Planner → EpistemicEngine → PolicyGuard → Executor      │
│  RULE: Every step is deterministic. No hidden state.               │
├─────────────────────────────────────────────────────────────────────┤
│  ⇓ approved trace                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  GROUNDED DOMAIN (material, irreversible)                          │
│  Git history, SQLite memory, graph state                           │
│  RULE: Only already-certified traces. No speculative writes.       │
└─────────────────────────────────────────────────────────────────────┘
```

### Containment Guarantee (Formal)

```
∀ event ∈ Plane1:
  ∃! trace ∈ Plane2:
    trace = execute(normalize(event))
    ∧ certified(epistemic(trace))
    ∧ safe(policy(trace))
    ⇒ project(memory, trace)
    ∴ ∀ mutation ∈ Grounded:
      provenance(mutation) = trace
      ∧ ¬ speculative(mutation)
      ∧ ¬ self_ authored(mutation)
```

**English:** For every event from Plane 1, there is exactly one execution trace through Plane 2. If that trace passes epistemic certification and policy safety, it is projected to memory. Every mutation in the Grounded domain has a verifiable provenance back to that trace — no speculative writes, no self-authored mutations.

### 10 Invariants (verifiable)

| # | Invariant | Domain | Verifiable by |
|---|-----------|--------|---------------|
| 1 | `kit-vantage` does not approve memory. It only certifies reality. | Bounded | Code review: `EpistemicEngine.verify()` returns Verdict only |
| 2 | PolicyGuard does not evaluate truth. It only governs traffic. | Bounded | Code review: no epistemic imports in `policy_guard.py` |
| 3 | MemoryRouter does not evaluate truth or safety. It only projects. | Grounded | Code review: no validation/decision in projection path |
| 4 | Memory is a deterministic consequence of truth, not a source of truth. | Cross-layer | Pipeline ordering: epistemic → write |
| 5 | No reverse flow from Plane 2 to Plane 1. | Cross-layer | No git write in runtime code |
| 6 | Runtime never mutates during planning. | Bounded | `ExecutionPlan(frozen=True)` |
| 7 | Single execution gate for all side effects. | Bounded | `RuntimeEngine._execute_step()` is only mutation path |
| 8 | **Cognition may be probabilistic. Reality transitions must be deterministic.** | Cross-layer | Same input → same output for all Plane 2 steps |
| 9 | Git anchors reality but does not define truth. | Grounded | Git is event source, not decision authority |
| 10 | **Hallucination is contained, not prevented.** | System | Unbounded never touches Grounded directly |

### Cross-Layer Constraints

```
Unbounded → Bounded:
  - Must pass through Intent Normalizer (trust boundary)
  - Must be a valid RawGitEvent or Intent signal
  - No raw LLM output can enter runtime directly

Bounded → Grounded:
  - Must pass through kit-vantage (epistemic gate)
  - Must pass through PolicyGuard (safety gate)
  - Only approved traces are projected

Grounded → Bounded:
  - FORBIDDEN: memory cannot trigger new intents
  - FORBIDDEN: graph cannot self-mutate

Grounded → Unbounded:
  - FORBIDDEN: no reverse flow at any level
```

### Semantic Smuggling Prevention

> All layers may transform structure, but none may infer intent beyond declared schema.

**Enforcement:**
- `IntentPayload`: only declared fields, no `_extra` or `_meta` injection
- `VerificationRequest`: only schema-defined fields
- `ProjectionRequest`: no `interpretation`, `inference`, or `meaning` fields
- `RawGitEvent`: no semantic annotation beyond event type

### Violation Response

| Violation | Response | Layer |
|-----------|----------|-------|
| Direct memory write | REJECTED by kit-vantage | Bounded |
| Intent chain > 3 | REJECTED by PolicyGuard | Bounded |
| Raw LLM output enters runtime | REJECTED by normalizer | Boundary |
| Memory triggers new intent | BLOCKED by architecture | Grounded |
| Graph self-mutation | BLOCKED by single write path | Grounded |
| Speculative memory write | REJECTED by epistemic gate | Bounded |

### Verifiable Properties (for Phase 10 integration tests)

```
P1: ∀ git_event: execute(git_event) ⇒ memory_integrity(git_event)
P2: ∀ pipeline: deterministic(pipeline) ⇒ reproducible(trace)
P3: ∀ mutation: provenance(mutation) ⇒ event_origin(mutation)
P4: ∀ rejection: reason(rejection) ∈ allowed_reasons(invariant_set)
P5: ∀ trace: chain_length(trace) ≤ max_depth(3)
```

### Summary

Kit is not a truth system. It is a **containment system**. The guarantee is not that cognition is correct — it's that incorrect cognition cannot materially corrupt the substrate.

---

## 3. EXECUTION: Execution Physics Spec v1.2.4

> v1.2.4 is already correct at runtime — now we are only writing down why it is correct.

### Invariants (Laws of Execution)

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

### Layer Mapping

```
┌─────────────────────────────────────────────────────┐
│ KIT CLI (Intent)                                     │
│   → kit learn / kit recall / kit doctor              │
├─────────────────────────────────────────────────────┤
│ MEMORYROUTER (Policy + Routing)                     │
│   → seal guard (I2)                               │
│   → canonicalization (I1)                          │
│   → routing decisions                            │
├───────────────────────────────────────────────────────┤
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

### Execution Flow Constraints

#### Valid Transitions

| From | Via | To |
|-----|-----|-----|
| working | commit | episodic |
| episodic | bake | semantic |
| semantic | archive | frozen |

#### Invalid Transitions (Enforced)

- working → frozen (must pass through semantic)
- uncommitted → persisted (seal guard blocks)
- orphaned → queryable (Vantage blocks)

### Sealing Boundary

```
UNCOMMITTED (working memory)
       ↓ seal guard (I2)
COMMITTED (episodic layer)
       ↓ bake (I5, I6)
BAKED (semantic layer)
       ↓ archive
FROZEN (immutable)
```

### Graph Integrity Rules

#### Edge Validity

- IMPORTS: source must import target
- INHERITS: source must extend target
- CALLS: source must call target (runtime reference)

#### Confidence Scoring

| Edge Type | Default Confidence |
|----------|-------------------|
| IMPORTS | 1.0 |
| INHERITS | 1.0 |
| CALLS | 0.7 (requires resolution) |

### Quick Reference

| Command | Layer | Invariant |
|---------|-------|----------|
| kit learn | MemoryRouter | I1, I2, I8 |
| kit recall | SAMBrain | I1, I7 |
| kit doctor | Vantage | I3, I4, I5 |
| kit commit | MemoryRouter | I2, I6 |
| kit bake | Vantage | I5, I6 |

### Non-Goals (Explicit)

- NOT a programming language spec
- NOT an API contract (use --help for that)
- NOT a migration guide (see MIGRATION.md)
- NOT a test suite
