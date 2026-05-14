# 🚀 KIT Release & Operation Journal

This document tracks the evolution of the KIT system, migration protocols, and release-specific hardening notes.

---

## 🛡️ v1.2.5 TITANIUM (Stable)
**Release Date:** 2026-05-14
**Focus:** Stateless Verification & Epistemic Authority

### Key Innovations
- **Stateless Verify Engine**: Decoupled `kit verify` from the `.kit` sentinel. Can run in pure ephemeral contexts (CI-ready).
- **Epistemic Ledger**: Introduced `kit_ledger.py` as the Single Source of Truth for component hashes.
- **Windows 11 Resilience**: Lock-free execution and path determinism for AI-integrated IDEs.

### Purged Artifacts
- Removed `research/`, `scratch/`, and `tests/phase10/` to harden the substrate.
- Deprecated legacy `.lock` files in favor of the Ledger.

---

## 🔒 Execution Contract v1.0
> **Status:** Locked Invariants for v1.2.x

1. **No Hidden Process Spawning**: Test isolation blocks subprocess kit CLI spawns to prevent IDE lag.
2. **No Global Filesystem Dependency**: All test state is scoped to `tmp_path` or `:memory:`.
3. **Deterministic Teardown**: Shutdown sequence includes `gc.collect()` and `time.sleep(0.2)` for Windows file handle safety.

---

## 🛠️ Safe Migration Protocol
Before any schema or structural change:
1. `kit snapshot`
2. Migrate on a DB copy.
3. `kit-vantage verify-memory -d`
4. `kit restore <verified_copy>`

### Operational Rules
- Never edit the SQLite database manually.
- Never delete L3 (Semantic/Frozen) records.
- Use `kit hygiene` for automated cleanup.

---

## 📜 Version History (Legacy)
- **v1.2.4**: Titanium Memory Integrity Pillar. Fixed scope hierarchy (Child > Parent).
- **v1.2.3**: Initial Titanium hardening.
