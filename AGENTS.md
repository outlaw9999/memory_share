# AGENTS.md — Canonical Behavioral Contract

## 🎯 MEMORY GATE

- No direct DB/FS access. No ad-hoc SQL/scripts.
- Operate via INTENTS only — never call kit CLI directly.

## 🧠 INTENT ROUTER (IR-C1) — v1.2.5

Agent MUST NOT call kit commands. Emit one of:

| Intent                         | Domain:Action              | When                        |
| ------------------------------ | -------------------------- | --------------------------- |
| `INTENT: GRAPH:BUILD`          | structural check           | structural check            |
| `INTENT: RELEASE:TEST`         | run unit tests             | run unit tests              |
| `INTENT: VERIFICATION:VERIFY`  | full integrity scan        | full integrity scan         |
| `INTENT: RUNTIME:HEALTH`       | env/schema diagnostics     | env/schema diagnostics      |
| `INTENT: MEMORY:MIGRATE`       | legacy memory path upgrade | legacy memory path upgrade  |
| `INTENT: RELEASE:RELEASE`      | release gate validation    | release gate validation     |
| `INTENT: MEMORY:LEARN`         | record cognitive observation| record cognitive observation|
| `INTENT: MEMORY:RECALL`        | retrieve context           | retrieve context            |

### Legacy single-token intents (backward compat)

| `INTENT: BUILD`   | → `GRAPH:BUILD`   |
| `INTENT: TEST`    | → `RELEASE:TEST`  |
| `INTENT: VERIFY`  | → `VERIFICATION:VERIFY` |
| `INTENT: HEALTH`  | → `RUNTIME:HEALTH`|
| `INTENT: MIGRATE` | → `MEMORY:MIGRATE`|
| `INTENT: RELEASE` | → `RELEASE:RELEASE`|
| `INTENT: LEARN`   | → `MEMORY:LEARN`  |
| `INTENT: RECALL`  | → `MEMORY:RECALL` |

Runtime maps intents → execution. The command surface is invisible.

## 🔄 LIFECYCLE HOOKS

startup (self_heal) → validate → execute → verify → recover

All lifecycle events resolve through the intent router.

| Event              | Intent                                |
| ------------------ | ------------------------------------- |
| ON_STARTUP         | `INTENT: RUNTIME:HEALTH`              |
| BEFORE_EDIT        | `INTENT: MEMORY:RECALL` (context)     |
| ON_UNKNOWN_SCHEMA  | `INTENT: VERIFICATION:VERIFY`         |
| ON_CORE_SYMBOL     | `INTENT: GRAPH:VERIFY`                |
| ON_FAIL            | `INTENT: RUNTIME:HEALTH`              |
| PRE_COMMIT         | `INTENT: LIFECYCLE:PRE_COMMIT`        |
| POST_COMMIT        | `INTENT: LIFECYCLE:POST_COMMIT`       |
| POST_MERGE         | `INTENT: MEMORY:RECONCILE`            |

## ⚡ FAST PATH (Dev Only)
- build → `task build` (or `python -m py_compile kit/**/*.py`)
- test  → `task test`  (or `pytest -q tests/`)

## 🛡️ RULES & ESCALATION

- Use `${workspaceFolder}` relative paths.
- Before mutation: emit `INTENT: RUNTIME:HEALTH`.
- On failure: `INTENT: VERIFICATION:VERIFY` → `INTENT: RUNTIME:HEALTH` → retry.
- Never call `kit ...` directly.
- Memory: Vantage (via `INTENT: VERIFICATION:VERIFY`)
- Logic: `pytest`
- Syntax: `py_compile`
