# AGENTS.md (v1.2.4-TITANIUM)

## 🧠 Kit System Contract

Kit is a deterministic workflow runtime for AI agents.

All operations MUST go through `kit` CLI.

---

## 🚀 Execution Model (Flow v0.1.2)

All multi-step tasks MUST use Flow Engine.

### Lifecycle
- PLAN → YAML DAG definition
- EXECUTE → step-level isolated execution
- COMMIT → final bake of results (`is_baked=1`)

No direct multi-step mutation outside Flow.

---

## 🧠 Memory Rules

- All knowledge is stored in `.kit/local_brain.db`
- Observations are **unbaked by default**
- Only COMMIT phase can set `is_baked=1`
- Never write directly to database

---

## ⚙️ CLI Contract

### Core
- `kit recall <query>` → retrieve memory
- `kit learn --content <text>` → store observation
- `kit stats` → system health

### Flow
- `kit flow run <file.yaml>` → execute workflow
- `kit flow list` → active flows
- `kit flow resume <id>` → resume failed flow

### Diagnostics
- `kit hygiene` → entropy + noise check
- `kit doctor --heal` → cleanup unsafe artifacts

---

## 🤝 Cross-Repo Rule

Any external repo using Kit MUST:

1. Start with:
   ```bash
   kit recall project_identity
   ```

2. Never bypass CLI → no direct DB access

3. All mutations MUST go through:
   - `kit learn`
   - or Flow Engine

4. All failures MUST be logged via:
   ```bash
   kit learn --tag friction
   ```

---

## 🏷️ Memory Tags

* invariant
* decision
* friction
* pattern
* skill
* note

---

## 📦 System State

Version: v1.2.4-TITANIUM
Runtime: Flow-enabled deterministic kernel
Mode: Production-ready (internal / controlled usage)
