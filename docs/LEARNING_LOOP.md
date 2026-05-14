# 🧠 Friction-Triggered Learning Loop (v1.2.5)

This document defines the deterministic, event-driven learning architecture of `kit` v1.2.5 (Titanium). It clarifies the boundary between system events and cognitive ingestion.

> [!IMPORTANT]
> **Applicability**: This Learning Loop applies strictly to **Class A: Cognitive Substrates**. It is forbidden in Class B/C repositories to avoid architectural pollution. See [SPECIFICATION.md#4-governance-boundary-classification--enforcement-v125](./SPECIFICATION.md) for details.

---

## 📊 The Loop Architecture

```mermaid
flowchart TD

%% ========== LAYER 1: GIT ==========
A[Git Event<br/>commit / merge / push] --> B[Git Hook Layer<br/>pre-commit / post-commit]

%% ========== LAYER 2: NORMALIZATION ==========
B --> C[RawGitEvent<br/>JSON emission]

C --> D[Intent Normalizer<br/>schema validation + cleanup]

%% ========== LAYER 3: TRUTH GATE ==========
D --> E[VANTAGE (Rust)<br/>Structural Verification]

E -->|PASS| F[VerifiedEvent]
E -->|FAIL| X[Reject Event<br/>no learning]

%% ========== LAYER 4: POLICY ==========
F --> G[PolicyGuard<br/>safety + routing rules]

G -->|ALLOW| H[MemoryRouter<br/>Write Boundary]
G -->|BLOCK| Y[Drop / Log Only]

%% ========== LAYER 5: LEARNING ==========
H --> I[kit learn<br/>deterministic ingestion]

I --> J[(SQLite .kit/local_brain.db<br/>L1/L2/L3/L4 memory layers)]

%% ========== FEEDBACK ==========
J --> K[kit recall / context query]
K --> A

%% ========== FRICITON LABEL ==========
style A fill:#1e1e1e,color:#fff
style E fill:#2d1b69,color:#fff
style H fill:#0f5132,color:#fff
style J fill:#0b7285,color:#fff
```

---

## 🧬 Core Principles (No Autonomous Agency)

Unlike autonomous agents that initiate self-reflection, `kit` operates strictly on an **event-sourced** model. Learning is a verified side-effect of system friction.

### 1. Git Hook = “Friction Sensor”
The hook is not the learning logic; it is simply a physical sensor detecting a change in the environment. If there is no commit or push, there is no trigger.

### 2. Vantage = “Truth Gate”
Vantage (the Rust-based forensic kernel) performs structural verification. It answers one question: *"Is this change structurally valid?"* It does not evaluate intent, only integrity.

### 3. PolicyGuard = “Traffic Controller”
Decides which events are eligible for memory ingestion based on pre-defined safety and routing rules.

### 4. MemoryRouter = “Write Boundary”
The most critical boundary. Learning only exists here. There is no "self-learning"; there is only "authorized writing" to the cognitive substrate.

### 5. `kit learn` = “Side-effect Executor”
Execution of the ingestion command is the final, deterministic step. It records an event that has already been verified and authorized.

---

## 🧭 The One-Sentence Truth

> **Kit does not learn from the world. Kit records changes in the world after they have been verified.**

---

## 🔒 Deterministic Constraints

* **No Autonomous Loop**: The system cannot trigger its own learning.
* **No Background Mutation**: State changes only happen during event processing.
* **No Hidden Evolution**: Every memory entry is traceable back to a `VerifiedEvent`.
