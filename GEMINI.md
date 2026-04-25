# GEMINI.md 

## 🔄 LIFECYCLE

startup (self_heal) → validate → execute → verify → recover

## ⚡ IDE HOOK LAYER

- ON_STARTUP        → python scripts/self_heal.py
- BEFORE_EDIT       → kit recall "`<intent>`"
- ON_UNKNOWN_SCHEMA → kit introspect --json
- ON_CORE_SYMBOL    → kit graph "`<path>`"
- ON_FAIL           → kit doctor

## ✅ VERIFICATION

- syntax: py_compile
- logic: pytest
- memory: kit-vantage verify-memory
