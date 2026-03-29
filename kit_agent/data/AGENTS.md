# AGENT COGNITIVE BOOTLOADER

> **STATUS:** Kit v1.2.3 STABLE
> **WARNING:** This file is the operating constitution, not the project memory database.

## 1. Mandatory Startup Sequence

Before taking action in this repository:

```bash
kit recall
```

Then read the docs in this exact order:

1. `AGENTS.md`
2. `docs/architecture.md`
3. `docs/playbook.md`
4. `docs/reference.md`

## 2. Iron Laws Of Memory

1. Never treat markdown as long-term memory. `.kit` is the authority.
2. Never guess paths or structure. Inspect the repo first.
3. Never store project business logic in this file.
4. Log friction with `kit learn --auto` or `scripts/kitf.ps1`.
5. Store decisions with short atomic entries.

## 3. Atomic Learn Protocol

- One idea per entry
- 20 words or fewer
- No explanation
- No special characters `>`, `|`, `&`
- Use simple natural language

## 4. Working Rules

- Break tasks into small steps
- Avoid long context accumulation
- Max autonomous attempts: 5, then surface the blocker
- Use `kit reflect` before risky changes
- Use `kit preflight` before commits when governance matters

## 5. Navigation Graph

1. `AGENTS.md`
2. `docs/architecture.md`
3. `docs/playbook.md`
4. `docs/reference.md`

## 6. Fast Start

```text
kit recall -> hydrate context
Inspect repo -> avoid blind edits
kit learn --auto -> capture friction
kit learn --tag decision --content "..." -> seal decisions
```

> If unsure, recall first and act later.

---

*Last Updated: 2026-03-29* | *v1.2.3*
