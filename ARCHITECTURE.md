# 🏛️ .kit Technical Architecture (v1.0.0)

`.kit` evolved from a raw memory engine (**SAM Epoch**) into a governed cognitive network (**AMSB Epoch**). This document defines its low-level internals and deterministic execution model.

## 🏛️ System Philosophy
`.kit` is a **Deterministic Cognitive OS** layer designed to synchronize memory across multi-agent environments. It rejects probabilistic retrieval (Vector/RAG) in favor of **Structural Integrity** and **Constitutional Governance**.

## 📊 The Quad-Store Schema (Compute-at-Write)
Memory is stored using SQLite + FTS5 in a 4-pillar architecture (Nodes, Observations, Edges, Commits). To ensure zero-lag IDE performance, mathematical ranking is computed at write-time (materialized).

### The Fact Ledger
```sql
CREATE TABLE observations (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    tag TEXT CHECK(tag IN ('invariant', 'decision', 'preference', 'note')) DEFAULT 'decision',
    materialized_score REAL NOT NULL DEFAULT 1.0, -- Pre-computed (Importance * Freq * Decay)
    scope TEXT,
    symbol TEXT, -- For Atomic Cognition (AST mapping)
    is_active BOOLEAN DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🧠 Cognitive Semantics Layer
facts are extended with semantic interpretation to enables higher-order reasoning:
- **`invariant`**: Hard architectural rules (e.g., "Auth must not call UI").
- **`decision`**: Intentional design choices (e.g., "Use SQLite for memory").
- **`preference`**: Style or local conventions (e.g., "Use snake_case").
- **`note`**: General informational noise.

## ⚖️ The Supreme Court (Arbitration Engine)
When conflicting memories are matched to a signal, the system invokes a deterministic arbitrator:

### 1. The Hard Guardrail
A lower-authority tag (`decision`) can **NEVER** override a higher-authority tag (`invariant`). Violations result in a hard `BLOCK`.

### 2. Additive Scoring Model
If authority is equal, conflicts are resolved via an additive formula to prevent exploding scores:
$$Score_{final} = MaterializedScore_{base} + Bonus_{type} + Bonus_{scope}$$
- **Type Bonus**: Invariant (0.3), Decision (0.2), Preference (0.1).
- **Scope Bonus**: Exact Match (0.3), Parent Match (0.2), Global (0.1).

### 3. Confidence Metrics
Confidence is calculated via **Competitive Margin**:
$$\text{Confidence} = \frac{Score_{winner} - Score_{loser}}{Score_{winner} + \epsilon}$$

## 🔄 Cognitive Execution Flow (Runtime)
The path from code change to persistent memory follows a strict 5-step loop:

1.  **Signal Detection**: The developer or agent modifies a file (captured by `kit watch` or IDE).
2.  **`recall()`**: Instantly retrieves $PWD-anchored memories matching the current scope/symbol.
3.  **`reflect()`**: 
    - Analyzes alignment between code and retrieved memories.
    - Considers all tags and resolves conflicts via the **Arbitrator**.
4.  **`preflight()`**: A blocking gatekeeper (Git Hook) that prevents `invariant` violations from reaching the repository.
5.  **`learn()`**: New decisions or fixes are committed to the ledger, updating the `materialized_score` for future recall.

## 🛡️ Runtime Components
1. **The Event Bus (`kit watch`)**: 200ms WAL polling emits semantic JSON events for real-time background agents.
2. **Cognitive Hygiene (`kit doctor`)**: Self-healing engine for safe deduplication and pruning of episodic noise.
3. **Runtime Anti-Lag**: Idempotent I/O ensures manifest files (`AGENTS.md`) are only written if the semantic hash changes.

## 🛡️ Stability & Versioning
- **Major**: Incompatible API or breaking schema changes.
- **Minor**: Additive functionality (backwards-compatible).
- **Patch**: Bug fixes and optimizations.
*Predictability is the ultimate feature of infrastructure.* 🏛️

---
*Last Updated: 2026-03-17 | Cognitive-Version: AMSB-15*
