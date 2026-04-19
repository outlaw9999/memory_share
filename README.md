# Memory Share Kit (v1.2.4-TITANIUM)

Deterministic long-term memory runtime for AI Agents and Developers.

## Philosophy
Kit is not a database; it is a **Cognitive Infrastructure**. It provides a durable, auditable, and ritualized memory kernel for autonomous systems.

## Quick Install
```bash
pip install memory-share-kit
```

## The Ritual (Essential for Agents)
1. **START**: `kit recall` (Load context)
2. **WORK**: `kit search <topic>` (Discover facts)
3. **END**: `kit learn` (Ingest decisions)

> **Quality Gate**: Before learning, ask: *"Is this worth remembering for 5 years?"* Keep signal density high.

## Safety Invariants
- **Never** modify `.kit/*.db` files manually.
- **Always** route operations through the `kit` CLI.
- **Seal** your workspace for production via `kit seal`.

## Architecture
- **L1 LOCAL**: Per-project episodic memory.
- **L2 GLOBAL**: Cross-project semantic knowledge.
- **L3 LAW**: Immutable system-wide invariants.
- **L4 TRACE**: Meta-awareness and decision logs.

---
License: MIT | Core: v1.2.4-TITANIUM
