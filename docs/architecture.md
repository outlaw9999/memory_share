# .kit Technical Architecture Specification (v1.2.3 STABLE)

> **Agent Navigation:** Read [../AGENTS.md](../AGENTS.md) first for rules, then [playbook.md](playbook.md) for practical workflow, and [reference.md](reference.md) for exact command syntax.

`.kit` is a deterministic memory OS and governance layer for human and agent workflows. This document defines the storage model, ranking model, governance boundaries, and intelligent routing system.

## 0. Release Status

- **Status:** Stable
- **Version:** v1.2.3
- **Focus:** Cognitive governance, air-gapped determinism, split-brain prevention, and resilient memory operations

## 0.1 Development Journey

`.kit` evolved through six architecture stages:

1. Core memory ledger (SQLite kernel)
2. Multi-agent integration (concurrency and fallback)
3. Semantic layer (deterministic ranking and conflict detection)
4. Resilience (circuit breakers and trust metrics)
5. Sensory nervous system (sensor contract v1, ephemeral memory)
6. Cognitive governance in v1.2.3 (auto-routing, firewall, idempotency, and absolute path isolation)

## 1. System Philosophy and Invariants

- **Zero Silent Failures:** Fail fast instead of degrading silently
- **Absolute Path Isolation:** The global brain lives at one unified OS path (`~/.kit/global.db`) to prevent multi-environment split-brain
- **Compute at Write:** Retrieval stays bounded through precomputed scoring
- **Immutable Ledger:** Memory is append-only by default
- **Air-Gapped by Default:** Core routing and classification do not require network access

## 2. Cognitive Governance (v1.2.3 Control Plane)

To prevent drift and memory pollution from autonomous agents, v1.2.3 introduces a strict rule-based auto-routing layer through `kit learn --auto`. For usage guidance, see [playbook.md](playbook.md). For exact command flags, see [reference.md](reference.md).

### 2.1 Noise Filter

Transient agent chatter such as "I will now..." or "Output generated" is detected through heuristics and dropped before it reaches the database.

### 2.2 Cognitive Firewall

Inputs are scanned with entropy checks and regex patterns. High-entropy strings containing likely secret markers such as `password=` or `sk-` are blocked from long-term memory.

### 2.3 Idempotency

The system computes a normalized `SHA-256` hash. Exact duplicates are skipped to prevent database bloat.

### 2.4 Abstraction Scorer

Inputs are scored on generality versus specificity.

- **Global Write Policy:** Only high-confidence generalized inputs should enter global memory
- **Downgrade Guard:** Inputs that are too specific are forced back to local memory

### 2.5 Execution Layers

The system is split into three execution layers to preserve determinism and performance.

#### L1: Fast Guard

- **Technology:** Regex and diff-based heuristics
- **Latency target:** under 50 ms
- **Role:**
  - Detect obvious violations early
  - Reject binary or oversized inputs
  - Avoid expensive downstream work when the input is already invalid
- **Constraint:** Must remain stateless

#### L2: Structural Analysis

- **Technology:** AST-based sensors such as Vantage
- **Role:**
  - Provide structural truth about code
  - Reduce ambiguity from raw text
- **Constraint:** Runs only if L1 passes

For structural usage notes and supported scope, see [integrations/vantage.md](integrations/vantage.md).

#### L3: Cognitive Governance

- **Technology:** SQLite plus invariants, scoring, and governance rules
- **Role:**
  - Enforce organizational rules
  - Detect drift and conflict
  - Produce the final decision
- **Constraint:** Must remain deterministic and air-gapped

#### Execution Principle

```text
L1 -> L2 -> L3
```

- If L1 fails: stop
- If L2 fails: stop
- Only L3 may produce the final governance decision

## 3. Sensor Contract v1

External sensors such as git hooks, IDE tooling, and CI pipelines can feed real-time signals into the agent workflow without polluting long-term memory.

### 3.1 Unix Pipe Protocol

Sensors communicate over `stdin` using JSON or structured text.

### 3.2 Ephemeral Fact Injection

Sensor outputs are injected under an ephemeral facts block in the agent prompt. These facts are high priority during the current task but are never stored automatically in SQLite.

## 4. Output Contract

To keep multi-model behavior predictable, responses should conform to a strict output contract:

```json
{
  "decision": "PASS | WARN | BLOCK",
  "reason": "Clear explanation of the decision",
  "confidence": "0.0 to 1.0"
}
```

## 5. Physical Storage Model

- **Engine:** SQLite in WAL mode
- **Concurrency:** Safe concurrent access across agents and IDEs
- **Encoding:** UTF-8 enforced across operating system boundaries

For maintenance commands such as `kit doctor`, `kit render`, and `kit watch`, see [reference.md](reference.md). For task flow around risky edits, see [playbook.md](playbook.md).

---

*Last Updated: 2026-03-29 | Version: v1.2.3 STABLE | Status: SEALED*
