# .kit Reference Guide (v1.2.3 STABLE)

This guide documents the active CLI and Python API surface for `.kit` v1.2.3.

## Runtime Support

`.kit` v1.2.3 supports Python `3.14.x`.

## Python API

```python
from pathlib import Path
import kit.api as api

api.init_kernel(Path(".kit/brain.db"))
```

### Core Functions

- `init_kernel(db_path: Path | None = None) -> None`
- `learn(uid, content, kind="observation", importance=0.5, metadata=None, layer="episodic", namespace="shared", agent_id=None, supersede_id=None, scope=None, to_global=False, symbol=None, structural_hash=None, skip_render=False) -> int`
- `search(query, limit=15, at=None, agent_id=None, fast=False) -> list[Any]`
- `recall(entities, limit=15, at=None, agent_id=None, here=False, symbol=None, fast=False) -> list[Any]`
- `recall_with_assessment(entities, limit=15, at=None, agent_id=None, here=False, symbol=None, fast=False) -> RankingAssessment`
- `export_prompt(entities, limit=3, budget=200) -> str`
- `reflect(diff_text, scope=None) -> Any`
- `preflight_check(commit_msg, strict=False) -> dict[str, Any]`

### Assessment States

- `HIGH_CONFIDENCE`
- `AMBIGUOUS`
- `WEAK_SIGNAL`
- `EMPTY`

## CLI

### Initialization

```bash
kit init
kit where
```

### Learn and Recall

```bash
kit learn --uid auth --tag invariant --content "Auth tokens must not be logged"
kit learn --uid cache --tag decision --content "Use SQLite for caching" --symbol cache_layer
kit learn --uid ui --tag note --content "Prefer local file logging for quick diagnostics"
kit learn --uid architecture_v1_2_3 --tag invariant --content "..." --no-render

kit recall auth
kit recall cache --here --symbol cache_layer
kit context --limit 5
kit search SQLite --limit 10
```

### Governance

```bash
kit reflect --mode advisory --here
kit preflight -m "check invariants"
kit blame validate_token
```

### Maintenance

```bash
kit doctor --mode safe
kit doctor --check-agents
kit doctor --reset-cloud
kit render
kit watch
```

## kit-agent

```bash
kit-agent status
kit-agent run "Design the cache layer"
kit-agent run "Implement payment flow" --provider local
kit-agent ask "Implement a login logger." --json
kit-agent reset-metrics
```

## Utility Scripts

```bash
python scripts/smoke_test_gemini.py
python scripts/smoke_test_full_local_gemini.py
python scripts/run_stress_test.py
python scripts/epoch_archive.py
```

## Troubleshooting

### kit-agent Provider Discovery Latency

Older `kit-agent` flows may experience long delays when provider discovery falls through sequential TCP checks. When that happens, use one of these supported workarounds:

#### Force a Healthy Provider

Bypass discovery and target a known working provider directly.

```bash
kit-agent ask "Your task" --provider gemini
```

#### Refuse Local Discovery Explicitly

If you do not run a local Jan or compatible local LLM endpoint, point discovery at a refusal port so the TCP stack fails immediately instead of waiting for a timeout.

```bash
# Unix/macOS/Linux
export JAN_BASE_URL="http://127.0.0.1:1"

# Windows (PowerShell)
$env:JAN_BASE_URL="http://127.0.0.1:1"
```

#### Verify Provider Health

```bash
kit-agent status
```

These workarounds preserve architecture lock while improving response time.

### Agent Runtime Guarantees

- Max repair loop attempts: `3`
- Local fallback is preferred when healthy cloud providers are unavailable
- Capacity failures trigger immediate cooldown-aware fallback
- Prompt injection uses the `.kit` assessment contract instead of raw retrieval alone
- Output contract is JSON with `decision`, `reason`, and `confidence`
- Exit codes are standardized at the `kit-agent` surface: `PASS/WARN=0`, `BLOCK=1`, `ERROR=2`

## Locked Prompt Export Contract

- Maximum Top-K memories: `3`
- Empty export returns an empty string
- Export uses compact first-line rendering
- Prompt budget defaults to approximately `200`

## See Also

- [README.md](../README.md)
- [architecture.md](architecture.md)
- [playbook.md](playbook.md)
- [integrations/vantage.md](integrations/vantage.md)

---

*Last Updated: 2026-03-29 | Version: v1.2.3 STABLE | Status: SEALED*
