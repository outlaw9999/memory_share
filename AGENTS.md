# AGENTS.md

## 🎯 MEMORY GATE

- No direct DB/FS access. No ad-hoc SQL/scripts.
- Operate via INTENTS only — never call kit CLI directly.

## 🧠 INTENT ROUTER (IR-C1)

Agent MUST NOT call kit commands. Emit one of:

| Intent            | When                        |
| ----------------- | --------------------------- |
| `INTENT: BUILD`   | structural check            |
| `INTENT: TEST`    | run unit tests              |
| `INTENT: VERIFY`  | full integrity scan         |
| `INTENT: HEALTH`  | env/schema diagnostics      |
| `INTENT: MIGRATE` | legacy memory path upgrade  |
| `INTENT: RELEASE` | release gate validation     |
| `INTENT: LEARN`   | record cognitive observation|
| `INTENT: RECALL`  | retrieve context            |

Runtime maps intents → kit execution. The command surface is invisible.

## ⚡ FAST PATH (Dev Only)
- build → `task build` (or `python -m py_compile kit/**/*.py`)
- test  → `task test`  (or `pytest -q tests/`)

## 🛡️ RULES & ESCALATION

- Use `${workspaceFolder}` relative paths.
- Before mutation: emit `INTENT: HEALTH`.
- On failure: `INTENT: VERIFY` → `INTENT: HEALTH` → retry.
- Never call `kit ...` directly.
