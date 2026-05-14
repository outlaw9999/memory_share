# GEMINI.md — v1.2.5

## 🔄 LIFECYCLE

startup (self_heal) → validate → execute → verify → recover

All lifecycle events resolve through the intent router. Never call kit CLI directly.

## ⚡ INTENT HOOK LAYER

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

## ✅ VERIFICATION

- syntax: py_compile
- logic: pytest
- memory: Vantage (via INTENT: VERIFICATION:VERIFY)
