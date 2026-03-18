# .kit - Deterministic Memory for AI Agents

`.kit` is a SQLite-backed memory and governance layer for developers and AI agents. It keeps architectural facts persistent, ranked, and deterministic across repeated runs without using embeddings or probabilistic RAG.

## AMSB v1.1 Stable

- Production-ready release line focused on deterministic memory, assessment, orchestration, and resilience
- Locked scope: no new features in this line, only bug fixes, maintenance, and documentation alignment
- Canonical architecture contract lives in [ARCHITECTURE.md](ARCHITECTURE.md)
- Generated manifests in `.kit/context` and `AGENTS.md` remain the highest local authority for agents

## What It Does

- `kit learn` stores explicit memories as `invariant`, `decision`, `preference`, or `note`
- `kit recall` retrieves ranked context deterministically for the current project or scope
- `kit reflect` detects memory gaps, drift, and invariant violations against a diff
- `kit preflight` enforces governance before code is committed
- `kit doctor` performs hygiene and agent-metric recovery tasks
- `kit-agent` runs provider orchestration with fallback, repair loops, and confidence-aware prompt injection

## Quickstart

```bash
# Initialize a project brain
kit init

# Learn an invariant
kit learn --uid auth_service --tag invariant --content "Auth tokens MUST NOT be logged"

# Recall scoped context
kit recall auth_service --here

# Run reflection on current changes
kit reflect --here

# Check agent health and reset persisted cloud cooldown state if needed
kit doctor --check-agents
kit doctor --reset-cloud

# Run the agent loop with provider fallback
python -m kit_agent.cli.main run "Implement payment flow"
```

## Stable Contracts

- Deterministic recall and ranking across repeated identical inputs
- Append-only fact ledger with `supersede` lineage
- Confidence states: `HIGH_CONFIDENCE`, `AMBIGUOUS`, `WEAK_SIGNAL`, `EMPTY`
- Prompt export constrained to Top-K `3` memories and approximately `200` characters of compact prompt budget
- SQLite WAL concurrency with bounded retry behavior

## Verification

- `pytest tests/ -v` is the canonical regression command for the locked v1.1 stable surface
- Coverage includes AMSB core behavior, deterministic ranking, reflection, provider fallback, protocol prompt injection, and chaos/resilience paths
- Behavioral and execution-model tests validate confidence-aware memory use against `semantic_mock` and fallback providers

## CLI Surface

```bash
kit learn --uid cache --tag decision --content "Use SQLite for caching"
kit learn --uid ui --tag note --content "Maybe prefer file-based logging locally"
kit recall cache --here
kit reflect --mode advisory
kit preflight -m "check invariants"
kit doctor --mode safe --check-agents
kit doctor --reset-cloud
```

## Python API

```python
from pathlib import Path
import kit.api as api

api.init_kernel(Path(".kit/brain.db"))
api.learn(uid="auth", content="JWT required", tag="decision")
assessment = api.recall_with_assessment(["auth"], limit=3, here=True)
prompt_block = api.export_prompt(["auth"], budget=200)
```

## Release Boundary

Out of scope for AMSB v1.1 stable:

- Vector search, embeddings, or semantic RAG retrieval
- Automatic resolution of conflicting invariants
- New product surface area outside memory, governance, orchestration, resilience, and verification

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [REFERENCE.md](REFERENCE.md)
- [AGENT_PLAYBOOK.md](AGENT_PLAYBOOK.md)
- [AGENT_PLAYBOOK.md](AGENT_PLAYBOOK.md) - see `Unix-Philosophy Locked` for the operating principles behind the stable line
- [MANIFESTO.md](MANIFESTO.md)

## License

MIT
