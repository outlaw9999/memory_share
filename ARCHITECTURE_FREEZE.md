# Architecture Freeze - Phase 6 (v0.1.0-phase6)

Status: FROZEN  
Effective date: 2026-03-08  
Scope: Kernel runtime contract for Phase 6

## 1) Frozen Kernel Interface

The following kernel capabilities are considered contract-stable for v0.1.0-phase6:

- `write_memory(...)` with Optimistic Concurrency Control (OCC)
- `read_node(...)` deterministic node read
- `append_node(...)` append semantics compatible with anchor-based mutation

**Kernel ABI version: 0.1**

Any change that alters input/output contract, error semantics, or OCC conflict behavior is a breaking change and must not be introduced in patch/minor work on this frozen line.

## 2) Frozen Core Invariants

- OCC guard: write is accepted only when knowledge state matches `expected_hash`.
- Journal protocol: intent/commit event stream remains authoritative for transactional recovery.
- Node identity: anchor-based addressing (HTML comments) remains the stable node identity mechanism.
- Crash/restart behavior: transaction state loader must support fast restart independent of journal growth.
- Journal Compatibility: The intent/commit format remains stable for downstream CDC consumers (e.g., ATLAS Indexer).

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

## 7) Post-Freeze Architecture Context

After this freeze, higher-level systems such as ATLAS (incremental code graph indexing) and memory query layers (Brain v2) are expected to integrate through the plugin boundary.

These systems must treat the kernel runtime as a stable substrate and must not rely on internal implementation details outside the frozen interface described above. The `kit` CLI serves as the official orchestrator for querying unified knowledge across these subsystems.

## 8) Query Interface

The system exposes a stable CLI query layer via `kit`.

Location:

- `kit.py`
- `kit_adapters.py`

Commands:

```text
kit symbol <query>
kit callers <symbol>
kit snippet <path>:<line>
kit context <symbol>
kit related <symbol>
```

Responsibilities:

| Command | Purpose |
| ------- | ------- |
| `symbol` | search indexed code symbols and related documentation |
| `callers` | inspect indexed call graph relationships |
| `snippet` | retrieve minimal code context from the filesystem |
| `context` | aggregate definition, call graph, snippet, and related notes in one query |
| `related` | explore neighboring symbols via similar names, graph edges, and module peers |

Data sources:

```text
Atlas -> code symbols + call graph
Brain -> documentation metadata
```

This query interface is considered stable and should remain backwards compatible for higher-level tooling, agents, and automation.
