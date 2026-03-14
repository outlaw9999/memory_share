# Architecture Freeze - Phase 6 (v0.1.0-phase6)

Status: FROZEN  
Effective date: 2026-03-08  
Scope: Kernel runtime contract for Phase 6

## 1) Frozen Kernel Interface

The following kernel capabilities are considered contract-stable for v0.1.0-phase6:

- `write_memory(...)` with Optimistic Concurrency Control (OCC)
- `read_node(...)` deterministic node read
- `append_node(...)` append semantics compatible with anchor-based mutation

Any change that alters input/output contract, error semantics, or OCC conflict behavior is a breaking change and must not be introduced in patch/minor work on this frozen line.

## 2) Frozen Core Invariants

- OCC guard: write is accepted only when knowledge state matches `expected_hash`.
- Journal protocol: intent/commit event stream remains authoritative for transactional recovery.
- Node identity: anchor-based addressing (HTML comments) remains the stable node identity mechanism.
- Crash/restart behavior: transaction state loader must support fast restart independent of journal growth.

## 3) Boundary Rules

Included in frozen kernel boundary:

- `runtime/kernel.py`
- `runtime/ast_parser.py`
- `runtime/journal_engine.py`
- `runtime/lock_manager.py`
- `runtime/paging_engine.py` (skeleton and extension points)

Outside kernel boundary (may evolve independently):

- Future graph/indexing systems (e.g., ATLAS)
- Plugin implementations
- Reporting/documentation content

## 4) Allowed Changes After Freeze

- Bug fixes that preserve API and invariants above
- Performance improvements with no externally visible behavior change
- Internal refactors that do not modify protocol, recovery semantics, or node identity rules

## 5) Not Allowed Without New Version Gate

- Changing function signatures or required parameters for frozen APIs
- Modifying OCC acceptance/rejection semantics
- Replacing anchor-based node identity in a non-backward-compatible manner
- Altering journal intent/commit compatibility or replay expectations

## 6) Versioning and Governance

- This freeze is tied to Git tag: `v0.1.0-phase6`.
- Breaking kernel changes require a new tagged release line (e.g., `v0.2.0+`) and migration notes.
- Phase 7 (ATLAS) must be integrated as a plugin-level concern, not by mutating frozen kernel contract.
