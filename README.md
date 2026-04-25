# 📦 memory-share-kit

> A lightweight cognitive runtime CLI for persistent memory + tool-driven reasoning.

---

## 🐍 Requirements

- **Python 3.14.x Required**
- This runtime is tested and supported strictly on Python 3.14.4+.

---

## ⚡ Install

```bash
pip install memory-share-kit
```

---

## 🚀 Quick Start

```bash
kit init
```

Initializes the local cognitive environment and seals the kernel.

```text
.kit/
  local_brain.db   (SQLite WAL + STRICT)
  config.json      (Runtime preferences)
```

---

## 🧠 Memory Topology

Kit enforces a **4-tier deterministic memory model**:

- **L1 — Local Brain**: Repository-specific reasoning and context.
- **L2 — Global Brain**: Shared user-level knowledge across projects.
- **L3 — Frozen Law**: Immutable architectural invariants (Read-Only).
- **L4 — Audit Trace**: Forensic log of all cognitive routing decisions.

---

## 🧠 Usage

### Store knowledge
```bash
kit learn --tag decision "Use WAL mode for deterministic writes"
```

### Recall context
```bash
kit recall
```

### Search memory
```bash
kit search "router failure"
```

### Verify integrity
```bash
kit-vantage verify-memory
```

---

## 🛡️ Core Principles

- **Runtime is Truth**: The executing environment is the only valid state.
- **CLI is Interface**: Clean, tool-first access to the cognitive kernel.
- **Memory is Persistent**: Deterministic storage with SQLite WAL + JSONB.
- **Verification is External**: Integrity is enforced by the **Vantage** sensor layer.

---

## ⚙️ Philosophy

> No repository knowledge required. Only runtime truth matters.

---

## 🛠️ Failure Recovery

If the system enters a friction state or memory drift is detected:

```bash
kit doctor          # Diagnose health
kit doctor --heal   # Automatically repair common artifacts
```

---

## 🧩 Commands Summary

```text
kit init                    Initialize environment
kit recall                  List active memories
kit search                  Full-text search (BM25)
kit learn                   Record new knowledge
kit doctor                  System health check
kit blast                   Analyze impact radius
kit graph                   Extract structural graph
kit-vantage verify-memory   Verify kernel integrity
```

---

## 📌 Version

v1.2.4.post1
