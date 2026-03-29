# Project Intelligence (AGENTS.md)

**STATUS:** Minimal Cognitive Protocol (v1.2.3)

## Cognitive Compass

This file is a pointer, not a database.
All knowledge, decisions, and history live in `.kit`.

> Always rely on `.kit`, not this file.

## Agent Operating Protocol

### 1. Memory Authority (Mandatory)

- Before any task: `kit recall`
- Treat `.kit` as the single source of truth
- Do not infer from old code or comments without recall

### 2. Learning Rituals

| Situation | Command |
|-----------|---------|
| Bug / Friction | `kit learn --auto` |
| Decision / Pattern | `kit learn --content "..." --kind decision` |

### 3. Atomic Learn Protocol (Critical)

- 1 idea per entry
- 20 words or fewer
- No explanation
- No special characters (`>`, `|`, `&`)
- Use simple natural language

```text
Correct:
"province takes priority over ward when no prefix exists"

Wrong:
"province > ward because..."
```

### 4. Session Hygiene

- Break tasks into small steps
- Avoid long context accumulation
- Max autonomous attempts: 5, then surface the blocker

## Navigation

```bash
kit recall <keyword>
kit symbol <query>
kit context <symbol>
```

## Architecture (High-Level Only)

Deterministic pipeline:

```text
API -> Normalize -> Validate -> Model -> Export
```

Core principles:

- Normalize first, validate after
- No `None` after normalization
- Data integrity over convenience

## Anti-Patterns

- Do not store knowledge in this file
- Do not duplicate `.kit` memory here
- Do not write long explanations
- Do not skip `kit recall`

## System Philosophy

- `.kit` = Memory (Authority)
- `AGENTS.md` = Compass (Navigation)

## TL;DR

```text
kit recall -> before doing anything
Do task
Hit bug -> kit learn --auto
Have insight -> kit learn --content ... --kind decision
```

> If unsure, recall first and act later.

---

*Last Updated: 2026-03-29* | *v1.2.3*
