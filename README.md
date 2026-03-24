# memory-share-kit

Deterministic memory and governance for AI agents.

## Install

```bash
pip install memory-share-kit
```

Requires Python 3.14.x only.

## Quick Start

```bash
kit init
kit learn --tag invariant --content "Auth MUST use JWT only."
kit-agent ask "Can I use session cookies?"
```

Expected: `DECISION: BLOCK`

## Core Commands

- `kit init` - Initialize memory space
- `kit learn` - store facts / invariants
- `kit recall` - retrieve memory
- `kit doctor` - system status
- `kit preflight` - governance gate
- `kit-agent ask` - run agent with memory

## Philosophy

Memory must be governed. If 10 agents ask the same question, they must get the exact same ranked facts.

> "Memory is not a luxury. It is a prerequisite for disciplined engineering."

### Principles
- Deterministic memory (SQLite, append-only)
- Same input → same decision
- Invariants override everything
- No dynamic data in long-term memory

## Daily Workflow

1. **Before task**: `kit recall <keyword>`
2. **During task**: `kit learn --auto` for friction, `kit learn --tag decision` for insights
3. **Before commit**: `kit preflight -m "<message>"`

## Contributing

- Python 3.14.x only (strict typing)
- No silent failures (fail-fast)
- `kit preflight` must pass before commit

## License

MIT