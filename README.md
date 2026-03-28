# .kit - Deterministic Cognitive Memory OS (v1.2.3)

> 🧭 **Agent Playbook**: For detailed AI instructions, see [AGENTS.md](AGENTS.md).
> 🏗️ **Technical Spec**: For architectural deep-dives, see [docs/architecture.md](docs/architecture.md).

`.kit` is a state-of-the-art memory kernel designed for the No-GIL era. It provides deterministic knowledge storage, atomic ingestion, and semantic retrieval for AI agents and human developers.

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

The common failure mode is an old editable install that still points at a renamed repo path, while the supported wrapper lives in `%USERPROFILE%\.local\bin\kit.bat` on Windows or `$HOME/.local/bin/kit` on Linux/macOS.

## ⚔️ The v1.2.3 Command Suite (Standard)

### 1. Atomic Knowledge Ingestion
Capture insights, decisions, and system invariants.
```bash
kit learn --tag invariant --content "Shared state must be immutable."
```

### 2. Semantic Query (Top-K Recall)
Retrieve distilled context without token bloat.
```bash
kit recall "concurrency"
```

### 3. Structural Mapping (Vantage)
Eliminate "Spatial Blindness" by mapping the repo architecture.
```bash
.\kit-vantage.bat
```

### 4. Friction Logging (The v1.2.3 Secret)
Record system friction to drive the v1.2.4 roadmap.
```bash
.\scripts\kitf.ps1
```

## 🛡️ Governance & Principles
- **Memory Isolation**: Local repo memory is strictly separated from global brain.
- **Identity Consistency**: Local git config (`So.Sai`) ensures verifiable provenance.
- **Zero-Footprint**: Root directory is kept clean. Databases live only in `.kit/`.

---
*Last Updated: 2026-03-28 | Version: v1.2.3 STABLE | Status: SEALED*
