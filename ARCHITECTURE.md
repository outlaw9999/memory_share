# .kit Technical Architecture Specification (v1.2.3 STABLE)

`.kit` is a deterministic memory OS and Cognitive Governance Layer for multi-agent and human workflows. This document defines the storage model, ranking model, governance boundaries, and the Intelligent Routing System.

## 0. Release Status

**Release Status:** STABLE (Merciless Stability)
**Version:** v1.2.3
**Focus:** Cognitive Governance, Air-Gapped Determinism, Split-Brain Prevention, and Stateful Resilience.

## 0.1 Development Journey

`.kit` evolved through six key architecture epochs:
1. **Stage 1**: Core Memory Ledger (SQLite Kernel).
2. **Stage 2**: Multi-Agent Integration (Concurrency & Fallback).
3. **Stage 3**: Semantic Layer (Deterministic Ranking & Conflict Detection).
4. **Stage 4**: Resilience (Circuit Breakers & Trust Metrics).
5. **Stage 5**: Sensory Nervous System (Sensor Contract v1, Ephemeral Memory).
6. **Stage 6 (v1.2.3)**: Cognitive Governance (Auto-Routing, Firewall, Idempotency, and Absolute Path Isolation).

## 1. System Philosophy & Invariants

- **Zero Silent Failures**: The system MUST fail fast rather than degrade silently (e.g., STDIN hangs are blocked).
- **Absolute Path Isolation**: The Global Brain exists at a single, unified OS path (`~/.kit/global.db`) to prevent multi-venv split-brain. Local Brains halt discovery at the `.git` root.
- **Compute-at-Write**: Read latency is O(log N) through precomputed scores.
- **Immutable Ledger**: Append-only fact stream.
- **Air-Gapped by Default**: Zero external network dependencies for routing and classification.

## 2. Cognitive Governance (The v1.2.3 Control Plane)

To prevent cognitive drift and memory pollution from autonomous agents, v1.2.3 introduces a strict, rule-based Auto-Routing layer (`kit learn --auto`).

### 2.1 The Noise Filter (Garbage Collection)
Transient agent chatter (e.g., "I will now...", "Output generated") is detected via heuristic pattern matching and explicitly **DROPPED** before touching the database.

### 2.2 The Cognitive Firewall (Secret Protection)
All inputs are scanned using Shannon Entropy and regex patterns. High-entropy strings containing keywords (e.g., `password=`, `sk-`) are strictly **BLOCKED** to prevent credential leakage into long-term memory.

### 2.3 Idempotency (Deduplication)
The system computes a `SHA-256` hash of the normalized input. Exact duplicate entries are detected and **SKIPPED** to prevent database bloat.

### 2.4 The Abstraction Scorer
Inputs are mathematically scored on Generality vs. Specificity:
- **GLOBAL Write Policy**: Only inputs exceeding a strict confidence threshold (Generality > 0.85) are allowed into the Global Brain.
- **Downgrade Guard**: Ambiguous or overly specific inputs attempting to write to Global are forcibly downgraded to the LOCAL Brain.

### 2.5 Execution Layers (Deterministic Separation)

To ensure performance, determinism, and architectural clarity, the system is strictly divided into three execution layers:

#### L1: Fast Guard (Preflight Filter)
- **Technology**: Regex, diff-based heuristics
- **Latency**: < 50ms
- **Role**:
  - Detect obvious violations (secrets, banned patterns).
  - Reject massive/binary commits early.
  - Prevent CPU-heavy downstream execution.
- **Constraint**:
  - MUST remain stateless.
  - MUST NOT replace structural or cognitive checks.

#### L2: Structural Analysis (External Sensors)
- **Technology**: AST (Vantage), language-aware parsing.
- **Role**:
  - Provide structural truth (imports, functions, call graph).
  - Eliminate ambiguity from raw text.
- **Constraint**:
  - Runs only if L1 passes.
  - Language-dependent, pluggable.

#### L3: Cognitive Governance (Core .kit)
- **Technology**: SQLite + invariants + scoring.
- **Role**:
  - Enforce organizational rules.
  - Detect drift, conflict, and semantic violations.
  - Make final decision.
- **Constraint**:
  - MUST remain deterministic and air-gapped.

#### Execution Principle
L1 → L2 → L3 (Strict Pipeline)
- If L1 fails → **STOP**.
- If L2 fails → **STOP**.
- Only L3 can produce the final governance decision.

## 3. Sensor Contract v1 (Sensory Nervous System)

External sensors (Git hooks, IDEs, CI/CD) pipe real-time signals into the agent's reasoning loop without polluting long-term memory.

### 3.1 Unix Pipe Protocol
Sensors communicate via STDIN using a standardized JSON or raw text format.

### 3.2 Ephemeral Fact Injection
Signals from the Sensor Contract are injected into the agent's prompt under the `[EPHEMERAL FACTS]` block. These facts are high-priority but **never** stored in the SQLite database.

## 4. Output Contract (Predictability)

To ensure multi-model consistency, all agent responses must conform to a strict Output Contract:
```json
{
  "decision": "PASS | WARN | BLOCK",
  "reason": "Clear explanation of the decision",
  "confidence": "0.0 to 1.0"
}
```

## 5. Physical Storage Model (SQLite)
- **Engine**: SQLite in WAL (Write-Ahead Logging) mode.
- **Concurrency**: Safe concurrent access by multiple agents across IDEs.
- **Encoding**: Strictly enforced UTF-8 across all OS boundaries (PYTHONUTF8=1).

---

*Last Updated: 2026-03-21 | Version: v1.2.3 STABLE | Status: SEALED*
