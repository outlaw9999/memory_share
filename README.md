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
- `kit learn`     # store facts / invariants
- `kit recall`    # retrieve memory
- `kit doctor`    # system status
- `kit-agent ask` # run agent with memory

## Principles
- Deterministic memory (SQLite, append-only)
- Same input → same decision
- Invariants override everything
- No dynamic data in long-term memory

## Notes
- Use `kit-agent` for runtime / dynamic context
- `kit learn` is for stable facts only
- Designed for CLI, scripts, and CI

## License
MIT
