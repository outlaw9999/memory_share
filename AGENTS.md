# AGENTS.md (KIT + VANTAGE v1.2.4 CONTRACT)

## 🔁 CORE LOOP

```text
introspect → recall → act → verify → learn
```

---

## 🧠 TRUTH RULE (ABSOLUTE)

* Không đoán
* Không hardcode schema
* Không đọc file trực tiếp
* Không commit hiểu biết tĩnh
* Mọi fact → phải qua tool runtime

---

## 🛠 TOOL CONTRACT

```text
unknown state   → kit introspect --json
context         → kit recall
search          → kit search
debug           → kit doctor
validate        → kit-vantage verify-memory
persist         → kit learn
help/schema     → <tool> --help (source of truth)
```

---

## 🔥 FAILURE LOOP

```text
kit doctor → introspect → recall → isolate → fix → verify → learn → re-verify
```

---

## 🚫 FORBIDDEN

* raw SQL / filesystem access
* schema guessing
* bypass router / vantage
* manual memory mutation
* test hacking / fake determinism
* docs > runtime truth

---

## 🧠 MEMORY LAW

```text
READ  = kit recall
WRITE = kit learn
CHECK = kit-vantage verify-memory
STRUCT = kit introspect
```

---

## ⚙️ SYSTEM PRINCIPLE

> Code is source of truth.
> Docs are only routing hints.
> CLI --help > Markdown.

---

## 🚀 EXECUTION MODEL

```text
INTENT
 → introspect
 → context (recall)
 → tool execution
 → verify (vantage)
 → persist (learn)
```

---

## ⚖️ FINAL LAW

> Nếu tool trả lời khác docs → tool thắng.
