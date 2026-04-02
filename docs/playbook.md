# Agent Playbook

This document is the practical operating manual for humans and agents working in this repository.

It is intentionally different from [AGENTS.md](../AGENTS.md):

- `AGENTS.md` defines mandatory behavioral rules and memory discipline
- `playbook.md` explains how to work effectively within those rules
- `reference.md` documents command and API details

## Use This File For

- Task flow
- Decision points during execution
- Recommended operating habits
- Troubleshooting entry points

Do not treat this file as the primary source for invariants. When a rule here conflicts with [AGENTS.md](../AGENTS.md), `AGENTS.md` wins.

## Recommended Workflow

### 1. Start with Recall

Before touching code, hydrate context:

```bash
kit recall
```

If the task is narrow, use a targeted query:

```bash
kit recall <keyword>
kit search <keyword>
kit context
```

For exact CLI syntax and related flags, see [reference.md](reference.md).

### 2. Decide Whether the Work Is Risky

Use the following rule of thumb:

- Small doc or text-only updates: proceed directly
- Code or schema changes with possible drift: run `kit reflect`
- Commit-time safety checks: run `kit preflight`

Example:

```bash
kit reflect --mode advisory --here
kit preflight -m "update architecture docs"
```

See [reference.md](reference.md) for command syntax and [architecture.md](architecture.md) for why the L1 -> L2 -> L3 flow exists.

### 3. Write Small, Atomic Memory Entries

Persist insights in a form that is easy to reuse:

- One idea per entry
- Keep entries short
- Prefer deterministic wording
- Use `--auto` for routine friction or operational learnings

Examples:

```bash
kit learn --auto --content "provider discovery falls through sequential TCP checks"
kit learn --content "wrapper sets PYTHONPATH and UTF8" --kind decision
```

The hard rules for memory discipline remain in [../AGENTS.md](../AGENTS.md).

### 4. Use the Right Memory Scope

- Use local memory for repo-specific facts, paths, shims, and incidents
- Use global memory for stable cross-repository tool behavior

Examples:

- Local: renamed repository path broke editable install
- Global: Vantage requires anchors to emit structural signals

### 5. Verify Operational Health & Metadata

Use maintenance commands to inspect, repair, or optimize the brain:

```bash
kit stats
kit where
kit doctor --mode safe
kit doctor --check-agents
```

### 6. Semantic Linking & Lifecycle

As a project matures, shift episodic memories to semantic anchors:

```bash
kit link --src auth --dst token --rel DEPENDS_ON
kit promote --threshold 10
kit bump <id>
kit label --id 42 --correct GLOBAL
```

### 7. Governance & Observability

Audit the codebase against project invariants:

```bash
kit blame <symbol>
kit render
kit watch
```

## Practical Decision Guide

### When to Use `kit learn --auto`

Use it when:

- you are logging friction (**Surgical Friction Logging**)
- you are not fully sure whether the fact belongs in local or global memory
- the content is short and operational

#### 🩸 Surgical Friction Logging (Hybrid v1.2.4 Mode)

During the "Desert Mode" observation phase, use [kitf.ps1](file:///e:/DEV/opensource_contrib/memory_share_kit/.kit/scripts/kitf.ps1) to capture forensic metrics. If you need a refresher on the expected schema, run:

```bash
kit recall forensic_friction_schema
```

Focus on:
- **Shim Stability**: Report any shell conflicts or execution delays.
- **Vantage Noise**: Capture cases where structural verification yields false positives.
- **Agent Drift**: Note when an AI agent fails to follow the mandatory startup sequence.

Avoid it when:
- you are recording a precise architectural decision with deliberate wording
- you need explicit control over tags, scope, or destination

### When to Use `kit reflect`

Use it before risky edits when:

- invariants may be affected
- changes cross module boundaries
- drift is more dangerous than speed

### When to Use `kit preflight`

Use it when:

- a commit is about to be created
- you want governance feedback in strict mode
- you want a final check against architectural memory

## Vantage Operating Notes

Vantage is a structural sensor, not a generic file hasher.

Use Vantage when:

- you need structural verification for supported code files
- you are inspecting anchored code regions

Do not use Vantage when:

- you only need a raw file checksum
- you are working with unsupported formats such as `.bat` or `.ps1`

For integration details, see [docs/integrations/vantage.md](integrations/vantage.md).

## Troubleshooting Map

- Memory and command behavior: [reference.md](reference.md)
- Architecture and execution layers: [architecture.md](architecture.md)
- Structural sensor integration: [integrations/vantage.md](integrations/vantage.md)
- Hard behavioral rules: [../AGENTS.md](../AGENTS.md)

## Design Principle

One fact should have one authoritative home:

- laws in `AGENTS.md`
- workflows in `playbook.md`
- command surface in `reference.md`
- architecture in `architecture.md`

That split keeps the repository easier for both humans and agents to parse quickly.
