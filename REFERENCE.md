# .kit Reference Guide (AMSB v1.1 Stable)

This guide captures the current CLI and Python API surface for the locked AMSB v1.1 stable line.

## Python API

```python
from pathlib import Path
import kit.api as api

api.init_kernel(Path(".kit/brain.db"))
```

### Core functions

- `init_kernel(db_path: Path | None = None) -> None`
- `learn(uid, content, kind="observation", importance=0.5, metadata=None, layer="episodic", namespace="shared", agent_id=None, supersede_id=None, scope=None, to_global=False, symbol=None, structural_hash=None) -> int`
- `search(query, limit=15, at=None, agent_id=None, fast=False) -> list[Any]`
- `recall(entities, limit=15, at=None, agent_id=None, here=False, symbol=None, fast=False) -> list[Any]`
- `recall_with_assessment(entities, limit=15, at=None, agent_id=None, here=False, symbol=None, fast=False) -> RankingAssessment`
- `export_prompt(entities, limit=3, budget=200) -> str`
- `reflect(diff_text, scope=None) -> Any`
- `preflight_check(commit_msg, strict=False) -> dict[str, Any]`

### Assessment states

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

### Learn and recall

```bash
kit learn --uid auth --tag invariant --content "Auth tokens MUST NOT be logged"
kit learn --uid cache --tag decision --content "Use SQLite for caching" --symbol cache_layer
kit learn --uid ui --tag note --content "Maybe prefer local file logging"

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
kit-agent reset-metrics
```

## Utility Scripts

```bash
python scripts/smoke_test_gemini.py
python scripts/smoke_test_full_local_gemini.py
python scripts/run_stress_test.py
python scripts/epoch_archive.py
```

### Agent runtime guarantees

- Max repair loop attempts: `3`
- Local fallback is preferred when healthy cloud providers are unavailable
- Capacity failures trigger immediate cooldown-aware fallback
- Prompt injection uses the `.kit` assessment contract instead of raw retrieval alone

## Locked prompt export contract

- Maximum Top-K memories: `3`
- Empty export returns an empty string
- Export uses compact first-line rendering
- Prompt budget defaults to approximately `200`

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [README.md](README.md)
