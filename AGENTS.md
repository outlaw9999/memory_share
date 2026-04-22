# AGENTS.md (v1.2.4 EXECUTION CONTRACT)

## ⚖️ FLOW
recall → tool → execute → learn

## 🚫 HARD PROHIBITIONS (NON-NEGOTIABLE)
These are not guidelines. Violation = broken invariant.

- **NEVER** access `*.db` files directly (no `sqlite3`, no file open).
- **NEVER** write or execute raw SQL against any brain database.
- **NEVER** bypass `MemoryRouter` to read/write memory.
- **NEVER** walk the filesystem to infer schema or memory state.
- **NEVER** write ad-hoc Python/shell scripts to inspect memory.
- **NEVER** guess parameters or API signatures.
- **NEVER** call internal runtime nodes (`MemoryRouter`, `SAMBrain`, `SchemaFactory`) directly.

If you feel the urge to do any of the above → STOP → call `kit doctor` first.

## 🧠 MEMORY ACCESS CONTRACT
ALL memory operations MUST go through exactly one of these three gates:

| Gate | Use for | Returns |
|---|---|---|
| `kit recall` | Reading context / knowledge | Structured memory entries |
| `kit search` | Locating a specific symbol/topic | Ranked results |
| `kit introspect --json` | Inspecting schema/command registry | JSON schema |

No other memory access path is permitted for an Agent.

## 🎯 ROUTING
- **Unknown schema/params** → `kit introspect --json`
- **Post-Arbitration Gate** → `kit-vantage verify --batch (MANDATORY)`
- **Startup / New Task** → `kit recall --limit 10`
- **Logic Conflict** → `kit-vantage verify-memory`
- **System State / Friction** → `kit doctor`
- **Persistence** → `kit learn --tag decision`

## 🔒 TOOL BOUNDARY (scope lock)
Each command has ONE purpose. Do not use a command outside its scope.

| Command | Permitted scope | Forbidden use |
|---|---|---|
| `kit recall` | Read structured memory | NOT a DB query tool |
| `kit learn` | Write tagged memory entry | NOT a file write tool |
| `kit doctor` | System health + self-heal | NOT a memory inspector |
| `kit introspect` | Export schema metadata only | NOT a runtime probe |
| `kit search` | Full-text memory search | NOT a file search tool |
| `kit stats` | Health pulse / GQI index | NOT a raw DB viewer |

## 🆘 ESCALATION
Fail → `kit-vantage verify` → `kit doctor` → `kit recall project_identity` → Retry
