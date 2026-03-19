# .kit Technical Architecture Specification (v1.2.0 GA)

`.kit` is a deterministic memory OS for multi-agent and human workflows. This document defines the storage model, ranking model, governance boundaries, and the Stage 5 Sensory Nervous System.

## 0. Release Status (GA)

**Release Status:** General Availability (GA)  
**Version:** v1.2.0  
**Focus:** Reliability, Cross-model Determinism, and Sensory Input.

## 0.1 Development Journey

`.kit` evolved through five key architecture stages:

1. **Stage 1**: Core Memory Ledger (SQLite Kernel).
2. **Stage 2**: Multi-Agent Integration (Concurrency & Fallback).
3. **Stage 3**: Semantic Layer (Deterministic Ranking & Conflict Detection).
4. **Stage 4**: Resilience (Circuit Breakers & Trust Metrics).
5. **Stage 5 - Sensory Nervous System**: Sensor Contract v1, Ephemeral Memory, and the cognitive friction layer.

## 1. System Philosophy And Invariants
- **Local Determinism**: Identical inputs yield identical context.
- **Compute-at-Write**: Read latency is O(log N) through precomputed scores.
- **Immutable Ledger**: Append-only fact stream.
- **Unix Composability**: Stream-first CLI (pipes are first-class citizens).

## 2. Cognitive Friction
The cognitive friction layer protects the memory ledger from cognitive drift by detecting and challenging non-deterministic data before it is stored as long-term architecture.
- **Detection**: Heuristic/Regex scan for percentages, metrics, timestamps, and temporal words.
- **Enforcement**: Warns on `invariant` and `decision` tags to force data into the Ephemeral layer.

## 3. Sensor Contract v1 (Sensory Nervous System)
Stage 5 introduces the ability for external sensors (Git hooks, IDEs, CI/CD) to pipe real-time signals into the agent's reasoning loop without polluting the long-term memory.

### 3.1 Unix Pipe Protocol
Sensors communicate via `stdin` using a standardized JSON or raw text format:
```json
{
  "sensor": "git-hook",
  "event": "pre-commit",
  "data": { "env": "production", "branch": "main" }
}
```

### 3.2 Ephemeral Fact Injection
Signals from the Sensor Contract are injected into the agent's prompt under the `[EPHEMERAL FACTS]` block. These facts are high-priority but **never** stored in the SQLite database.

## 4. Output Contract (Predictability)
To ensure multi-model consistency (Gemini ↔ Jan), all agent responses must conform to a strict Output Contract:
```json
{
  "decision": "PASS | WARN | BLOCK",
  "reason": "Clear explanation of the decision",
  "confidence": "0.0 to 1.0"
}
```

## 5. System Invariants enforcement
Prompt injection includes `[STRICT EXECUTION RULES]` to force the LLM to respect memory invariants:
1. **Rule Override**: Memory invariants override all external training/suggestions.
2. **Decision Layer**: If a request violates an invariant, the agent MUST return `BLOCK`.
3. **No Ambiguity**: Non-deterministic answers ("it depends") are banned for invariant checks.

## 6. Physical Storage Model (SQLite)
The ledger remains an append-only SQLite database using WAL mode for safe concurrent access by multiple agents.

---

*Last Updated: 2026-03-19 | Version: v1.2.0 GA*
