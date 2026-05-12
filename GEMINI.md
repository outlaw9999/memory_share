# GEMINI.md

## 🔄 LIFECYCLE

startup (self_heal) → validate → execute → verify → recover

All lifecycle events resolve through the intent router. Never call kit CLI directly.

## ⚡ INTENT HOOK LAYER

| Event              | Intent                     |
| ------------------ | -------------------------- |
| ON_STARTUP         | `INTENT: HEALTH`           |
| BEFORE_EDIT        | `INTENT: RECALL` (context) |
| ON_UNKNOWN_SCHEMA  | `INTENT: VERIFY`           |
| ON_CORE_SYMBOL     | `INTENT: VERIFY` (graph)   |
| ON_FAIL            | `INTENT: HEALTH`           |

## ✅ VERIFICATION

- syntax: py_compile
- logic: pytest
- memory: Vantage (via INTENT: VERIFY)
