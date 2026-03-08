# .kit Architecture Freeze

Status: **Frozen since v1.0.0**

The `.kit` engine architecture is considered stable and **must not be structurally modified**. All future capabilities must be implemented **without changing the core schema or engine design**.

---

## Core Philosophy

The `.kit` system follows a minimal AI-native architecture:

* **SQLite over Servers**
  All intelligence runs on a local SQLite engine. No external services or daemons.
* **Query-time Intelligence**
  System capabilities are implemented as SQL queries, not engine logic.
* **Token-efficient Outputs**
  Outputs must be optimized for LLM consumption (prefer structured JSON).
* **Agent-first Design**
  The system is designed primarily for AI agents rather than human-oriented UI tools.

---

## Architectural Rules

The following rules are mandatory for all future contributions:

1. **Schema Freeze**
   The `.kit` SQLite schema (`symbols`, `calls`, `applied_txns`) must remain unchanged after v1.0.
2. **Query-only Evolution**
   New intelligence must be implemented as SQL queries in the Agent Layer.
3. **No Infrastructure Expansion**
   Do not introduce servers, caches, brokers, or microservices.
4. **Deterministic Execution**
   All queries must produce stable, reproducible results.
5. **LLM-Compatible Outputs**
   Priority is given to structured JSON outputs over human-oriented formatting.

---

## Anti-Patterns (Strictly Forbidden)

The following architectural patterns are incompatible with `.kit` and must never be introduced:

* ❌ **Active Daemons / Background Workers**: `.kit` must remain a passive CLI tool.
* ❌ **ORMs or Graph Abstraction Layers**: SQLite must remain directly accessible via raw SQL.
* ❌ **Agent-written State**: Agents must never write reasoning, logs, or memory into the `.kit` database.
* ❌ **Network Dependencies**: The engine must operate fully offline. No cloud services or remote analysis.
* ❌ **Infrastructure Expansion**: Do not introduce Redis, Kafka, or any message brokers.
* ❌ **Schema Mutations**: The SQLite schema is frozen to protect the contract with Agents.
* ❌ **Human-optimized Formats for Agents**: ASCII diagrams or verbose text must not replace JSON.
* ❌ **Hidden Intelligence Layers**: Intelligence must remain transparent SQL, not opaque code.

---

## Extension Strategy

Future features must follow this deterministic pattern:
**Code → SQLite Graph → SQL Query → LLM Reasoning**

This ensures the engine remains minimal while intelligence grows through the query layer.
