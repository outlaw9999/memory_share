# AGENTS.md (v1.2.4-TITANIUM)

## 🏗️ The Titanium System Contract

Kit is not a tool; it is a **Deterministic Workflow Runtime Kernel** for AI agents. This document defines the protocol for all agents interacting with this repository.

> **Mantra:** AI learns, remembers, obeys. Skills do not learn; Agents learn from Skills. IDE is the UI layer of Kit.

---

## 🚀 Execution Model: Flow v0.1.2

Multi-step tasks MUST be orchestrated via the **Flow Runtime**. Agents are prohibited from executing raw scripts for complex state mutations.

### 🏁 3-Phase Lifecycle
1.  **PLAN**: Define a YAML DAG. Resolve dependencies. Detect circularity.
2.  **EXECUTE**: Step-level isolation. Each step is a `Transaction`. Side-effects are tagged but unbaked.
3.  **COMMIT**: Finalize truth. Bulk "bake" observations (`is_baked=1`) only after full success.

### 🛠️ How to run work
```bash
# 1. Analyze task and load context
kit recall project_identity

# 2. Execute via Flow Engine
kit flow run <task.yaml>

# 3. Verify results
kit recall <result_uid>
```

---

## 🧠 Memory Topology & Rules

### 📊 The 4-Tier Hierarchy
1.  **L1: Local** (`.kit/local_brain.db`) - Project episodic memory.
2.  **L2: Global** (`~/.kit/global_brain.db`) - Institutional skills.
3.  **L3: Law** (`~/.kit/global_read_only.db`) - **IMMUTABLE** invariants.
4.  **L4: Trace** (`~/.kit/router_decisions.jsonl`) - Append-only cognitive audit trail.

### 🛡️ Transactional Memory Contract
- **Learning**: Every `kit learn` must be governed by an `ExecutionFrame`.
- **Isolation**: Observations generated within a Flow are `is_baked=0`.
- **Baking**: Truth is crystallized only after a successful `COMMIT` phase.
- **Purge**: Failed transactions allow for deterministic purging of "hallucinated" side-effects.

---

## ⚙️ Command Interface (ABI)

### 🧠 Memory Layer
- `kit recall <query>`: Retrieve ranked context.
- `kit learn --content <text> --tag <tag>`: Ingest new truth.
- `kit search <query>`: Hybrid FTS5 + Semantic search.

### 🧱 Core Runtime
- `kit flow run <path>`: Execute a workflow DAG.
- `kit flow list`: Show active/failed flow transactions.
- `kit flow doctor`: Repair stuck execution states.

### 🧪 Diagnostic Layer
- `kit stats`: Audit brain density and entropy.
- `kit hygiene`: Classify artifacts and detect noise (Entropy target < 0.10).
- `kit doctor --heal`: Execute Cleanup DAG to purge noise.

---

## 🤝 Cross-Repository Protocol

External agents or repositories interacting with this Kit instance MUST:

1.  **The Handshake**: Always start the session with `kit recall project_identity`.
2.  **No Direct I/O**: Never write directly to `.db` files. All mutations must use the `kit` CLI or API.
3.  **Environment Lock**: Always run within the project's `.venv`. Use `python -m kit` if the `kit` alias is missing.
4.  **Log Friction**: If a flow fails or a lock is encountered, use `kit learn --tag friction`.

---

## 🏷️ The 9-Tag SSOT
- `invariant`: System laws (Immutable).
- `decision`: Architectural commitments.
- `friction`: Roadblocks encountered.
- `preference`: UX and stylistic choices.
- `note`: Contextual observations.
- `skill`: Reusable procedural logic.
- `pattern`: Reoccurring design solutions.
- `hypothesis`: Unverified assumptions.
- `legacy`: Deprecated patterns to avoid.

---

*Last Synchronized: 2026-04-18 (v1.2.4-STABLE)*
