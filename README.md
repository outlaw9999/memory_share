# .kit - Deterministic Memory OS for Multi-Agent Systems

> "LLMs forget. .kit remembers deterministically."

`.kit` is a SQLite-backed memory and governance layer for AI agents. It maintains an append-only ledger of facts, decisions, and invariants, then uses deterministic ranking and protocol enforcement to turn stochastic model output into a controlled system.

## Core Philosophy

- **Determinism First**: Identical inputs should yield identical ranked context.
- **Immutable Ledger**: Facts are not silently deleted; they are superseded by newer truths.
- **Cognitive Friction**: Dynamic or temporal data is detected and challenged before it is stored as long-term architecture.
- **Unix Composability**: The CLI is designed for pipes, scripts, and stateless orchestration.

## The Golden Path

```bash
kit init
kit learn --tag invariant --content "Auth tokens MUST NOT be logged to console."
kit-agent ask "Implement a login logger."
```

Result: `DECISION: BLOCK`

## Cognitive Friction

`.kit` is not a log aggregator or metrics store. `kit learn` warns and challenges content that looks dynamic, such as:

- percentages or latency measurements
- CPU or RAM metrics
- timestamps or temporal words such as `currently` and `now`

Dynamic signals should go to `kit-agent` as ephemeral facts instead of being stored as long-term memory.

In v1.2.0 this is a friction layer, not a hard block:

- interactive use asks for confirmation
- non-interactive use emits a warning and continues

## Ephemeral Memory

```bash
echo '{"env":"prod","version":"1.2.0"}' | kit-agent ask "What is the environment?"
```

## CLI Surface

- `kit learn`: ingest observations, invariants, and decisions
- `kit recall`: retrieve ranked context for a symbol or scope
- `kit reflect`: detect memory gaps and architectural drift in a diff
- `kit doctor`: inspect system and agent health
- `kit-agent run` or `kit-agent ask`: execute a task with provider fallback and structured output

## Installation

```bash
pip install memory-share-kit
```

Python `3.14.x` is the only supported runtime for this release line. If you need another Python version, fork it.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [REFERENCE.md](REFERENCE.md)
- [AGENT_PLAYBOOK.md](AGENT_PLAYBOOK.md)

## License

MIT
