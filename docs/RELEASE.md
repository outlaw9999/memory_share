# RELEASE NOTES - v1.2.5 TITANIUM

## 🚀 Overview: The Balanced Titanium Protocol
Version 1.2.5 (Titanium) marks the transition of `memory-share-kit` from a tool to a **foundational semantic infrastructure protocol**. We have achieved a critical architectural balance: a lightning-fast cognitive runtime for agents combined with a forensic-grade structural verification sidecar.

---

## 🏗️ The 7 Phases of Achievement

| Phase | Innovation | Impact |
| :--- | :--- | :--- |
| **1-2** | **Unified Semantic Identity** | Established a singular, immutable ID system for code and memory. |
| **3** | **Deterministic Extraction** | Guaranteed 1-to-1 reproducible AST-to-Signal mapping. |
| **4** | **Architectural Intent Layer** | Gated memory writes by verified structural intent (Vantage). |
| **5** | **Stable Operator Interface** | Hardened CLI/API against environmental and platform drift. |
| **6** | **Semantic Law Enforcement** | Integrated Constitutional Admission Layer (CAL) for repo-bound truth. |
| **7** | **Temporal Drift Forensics** | Enabled deep, point-in-time structural evolution auditing. |

---

## 💎 Key Innovations in v1.2.5

### 1. Friction-Triggered Learning
Kit no longer "autonomous learns" from the world. It records changes in the world after they have been verified through the Git-to-Vantage pipeline. See [LEARNING_LOOP.md](./LEARNING_LOOP.md).

### 2. Runtime/Forensic Decoupling
- **Cognitive Hot-Path**: `learn`, `recall`, and `stats` are now local-only, zero-subprocess, and optimized for low-latency IDE agent workflows (~40ms).
- **Forensic Sidecar**: `vantage`, `doctor`, and `verify` provide deep structural truth without blocking daily execution.

### 3. Constitutional Admission Layer (CAL)
Self-attested repository identity in `pyproject.toml` is verified against structural evidence, preventing identity smuggling and architectural pollution. See [SPECIFICATION.md](./SPECIFICATION.md).

---

## 🛠 Usage for Agents
Agents should focus on the four core primitives for maximum stability:
1. `kit learn` - Record a fact.
2. `kit recall` - Retrieve context.
3. `kit search` - Query memory.
4. `kit status` - Check health.

---
*Signed, The Architect.*
