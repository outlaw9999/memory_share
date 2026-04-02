# .kit - Deterministic Cognitive Memory OS (v1.2.3)

> **Agent Navigation:** Read [../AGENTS.md](../AGENTS.md) first for rules (now back in the project root), then [playbook.md](playbook.md) for practical workflow, and [reference.md](reference.md) for exact command syntax.
> **Technical Spec:** For architecture details, see [docs/architecture.md](docs/architecture.md).

`.kit` is a deterministic memory kernel for developers and AI agents. It provides persistent memory, ranked recall, governance checks, and operational hygiene without requiring network access for core memory behavior.

## Packaged For Other Repositories

The v1.2.3 package is meant to onboard agents in other repositories without carrying over repo-specific business memory.

What ships for agents:

- a sterile [AGENTS.md](AGENTS.md) bootloader with startup laws
- [docs/architecture.md](docs/architecture.md) for the system blueprint
- [docs/playbook.md](docs/playbook.md) for workflow guidance
- [docs/reference.md](docs/reference.md) for the full `kit` and `kit-agent` command surface
- [docs/integrations/vantage.md](docs/integrations/vantage.md) for structural sensor behavior

Expected startup in a fresh repo:

```bash
kit recall
```

`kit init` now does three onboarding steps for a fresh repository:

- Creates a sterile `AGENTS.md` bootloader in the project root.
- Copies `reference.md` and `kitf.ps1` into `.kit/docs/` and `.kit/scripts/`.
- Seeds a small local starter pack into `.kit/brain.db`.

## What It Does

- Stores project and global memory in SQLite
- Supports atomic `learn`, ranked `recall`, and keyword `search`
- Enforces governance through `reflect`, `preflight`, and `doctor`
- Separates local and global memory to reduce cross-project pollution
- Supports agent workflows through `kit-agent` and sensor integrations such as Vantage

## Installation

Windows:

```powershell
.\install.bat
```

Linux/macOS:

```bash
./install.sh
```

If `kit` fails with `ModuleNotFoundError: No module named 'kit'`, first check whether a stale editable install is shadowing the wrapper:

```powershell
python -m pip show memory-share-kit
python -m pip uninstall memory-share-kit
```

The most common failure mode is an old editable install that still points to a renamed repository path, while the supported wrapper lives in `%USERPROFILE%\.local\bin\kit.bat` on Windows or `$HOME/.local/bin/kit` on Linux/macOS.

## Standard Command Suite

### 1. Atomic Knowledge Ingestion

Capture insights, decisions, and invariants.

```bash
kit learn --tag invariant --content "Shared state must be immutable."
```

### 2. Semantic Recall

Retrieve distilled context without token bloat.

```bash
kit recall concurrency
```

### 3. Structural Mapping

Use the Vantage shim to inspect repository structure.

```bash
.\kit-vantage.bat
```

### 4. Friction Logging

Record recurring friction so the system can learn from it.

```bash
.\scripts\kitf.ps1
```

## Governance Principles

- **Memory Isolation:** Local repository memory stays separate from global memory.
- **Identity Consistency:** Local git identity should remain intentional and auditable.
- **Zero-Footprint:** Operational data belongs in `.kit/`, not in random root files.
- **Determinism:** The same input should produce the same stored or recalled result under the same state.

## Documentation Map (Initialized Projects)

- `AGENTS.md`: agent operating rules and memory discipline
- `.kit/docs/reference.md`: full CLI and API reference for `kit` and `kit-agent`
- `.kit/scripts/kitf.ps1`: local task friction logger

---

*Last Updated: 2026-03-29 | Version: v1.2.3 STABLE | Status: SEALED*
