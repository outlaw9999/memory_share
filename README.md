# 📦 memory-share-kit

> A lightweight cognitive runtime CLI for persistent memory + tool-driven reasoning.

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

Creates local brain storage:

```text
.kit/
  local_brain.db
  config.json
```

---

## 🧠 Ask the system

```bash
kit-agent ask "What is your memory structure?"
```

---

## 🧾 Store memory

```bash
kit learn --tag decision "Use WAL mode for deterministic writes"
```

Tags:

* invariant
* decision
* friction
* preference
* note
* legacy
* skill
* pattern
* hypothesis

---

## 🔍 Recall

```bash
kit recall
```

or

```bash
kit search "router failure"
```

---

## 🧪 Debug (dev only)

```bash
kit doctor
```

---

## 🛡 Verify integrity

```bash
kit-vantage verify-memory
```

---

## 🧠 Core Principle

* Runtime is truth
* CLI is interface
* Memory is persistent
* Verification is external (Vantage)

---

## ⚙️ Philosophy (1 line)

> No repo knowledge required. Only runtime matters.

---

## 🧩 Commands summary

```text
kit init
kit-agent ask
kit recall
kit search
kit learn
kit doctor
kit-vantage verify-memory
```

---

## 📌 Version

v1.2.4-sealed
