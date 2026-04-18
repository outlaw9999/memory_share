# AGENTS.md (v1.2.4)

Kit = deterministic workflow runtime for AI agents.

---

## Entry Rule

Always start with:

```bash
kit recall project_identity
```

---

## Core Principle

* CLI is the only interface
* No direct DB access
* No manual state mutation

---

## Execution Model

Use Flow Engine for multi-step work:

PLAN → EXECUTE → COMMIT

---

## Memory Rule

All facts go through:

* kit learn
* kit recall

Use `kit learn --help` for valid tags (authoritative source).

---

## Flow Rule

kit flow run <yaml>

All side effects must be inside Flow.

---

## Vantage Rule

Use Vantage for validation:

kit-vantage verify <file>

---

## Failure Rule

On error:

kit learn --tag friction

---

## System State

v1.2.4-TITANIUM
Mode: deterministic runtime kernel
