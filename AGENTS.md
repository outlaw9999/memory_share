# AGENTS.md (v1.2.4 CONTRACT)

## ⚖️ FLOW
recall → tool → execute → learn

## 🎯 ROUTING
- unknown schema -> kit introspect --json
- startup        -> kit recall --limit 10
- friction       -> kit doctor
- conflict       -> kit-vantage verify-memory
- persist        -> kit learn --tag decision

## 🧠 MEMORY GATE
ALL memory access MUST go through:
- kit recall          -- read context
- kit search          -- locate symbol/topic
- kit introspect --json -- inspect schema

## 🚫 HARD RULES
- no direct DB access
- no raw SQL
- no filesystem inference
- no bypass MemoryRouter
- no ad-hoc scripts to inspect memory

## 🆘 ESCALATION
fail -> kit-vantage verify -> kit doctor -> retry
