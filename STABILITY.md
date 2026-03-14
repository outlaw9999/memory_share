# 🛡️ .kit Stability & Support (v2.0+)

This document outlines the commitment of `.kit` (memory_share) to long-term stability, reliability, and predictability. As an infrastructure-grade engine, we prioritize a stable foundation over rapid characteristic changes.

## 1. API Stability Guarantees
- **v2.x Branch**: The public API defined in `kit/api.py` is considered **Stable**. 
- **Breaking Changes**: Any change that breaks existing integrations will trigger a major version bump (e.g., v3.0).
- **Deprecation Policy**: Features scheduled for removal will be marked as deprecated for at least one minor release cycle (vX.Y to vX.Y+1).

## 2. Schema Freeze (SAM V2)
- The core SQLite schema for `entities`, `facts`, and `relations` is **Frozen**.
- **Evolution**: Any necessary schema changes will be additive (e.g., new optional columns or tables) and must include automated migration scripts.
- **Deterministic Ranking**: The core mathematical heuristic for scoring is a fundamental part of the engine stability and will not change without a significant architectural review.

## 3. Versioning Policy
We strictly follow [Semantic Versioning 2.0.0](https://semver.org/):
- **MAJOR**: Incompatible API or architectural changes (e.g., the v1 to v2 SAM Pivot).
- **MINOR**: Additive functionality in a backwards-compatible manner (e.g., batch-learn, namespaces).
- **PATCH**: Backwards-compatible bug fixes and performance optimizations.

## 4. Maintenance & Cleanup
- **Engine First**: The core engine (`kit/core`) will remain zero-dependency and minimal.
- **Plugins**: Experimental or domain-specific features (e.g., AST parsing, Git analysis) reside in the `plugins/` directory and do not carry the same stability guarantees as the core engine.

---
*Predictability is the ultimate feature of infrastructure.* 🏛️
