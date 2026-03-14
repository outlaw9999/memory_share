# 🧠 .kit

**Persistent memory for your terminal. Local-first. Powered by SQLite.**

Stop forgetting architecture decisions, weird bugs, and complex commands. `.kit` is a git-like memory ledger for you and your AI agents.

### ⚡ The 10-Second Demo

```bash
$ pip install kit-engine

$ kit learn bug "Fixed memory leak in Auth by dropping JWT for RS256"
✅ Learned (ID: 1)

$ kit recall auth
[auth] (Score: 0.1505) -> Fixed memory leak in Auth by dropping JWT for RS256
```

### 🛠️ Why .kit?

* **Zero Cloud & Zero API:** Everything lives locally in `~/.kit/brain.db`. 100% private.
* **Deterministic:** No vector hallucinations. It's a structured graph of facts.
* **Lineage & Evolution:** Automatically hides stale info using `supersedes_id`. Tri thức luôn tiến hóa.
* **CLI-First Architecture:** Built for the pipe. Works perfectly with `fzf`, `grep`, and AI Agents (Cursor/Windsurf).

### 📦 Usage

**Humans:**
```bash
kit learn arch "We chose Postgres over MongoDB because of ACID compliance"
kit recall arch
```

**Agents (Cursor / Windsurf / CLI Agents):**
Agents prefer CLI commands over complex SDKs. Just tell your agent: *"Check my .kit memory for the last architecture decision."*

### 🚢 Installation
```bash
pip install kit-engine
```

---
*Small. Fast. Reliable. Built for the era of Humans and Agents.*
⚔️🚀🛡️🧠🥂
