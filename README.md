# 🧠 .kit — Deterministic Memory for AI Agents

> **Without memory, agents hallucinate. .kit fixes that.**
> 
> AI agents suffer from a fatal flaw: **They have amnesia.** Context windows reset. Architectural rules are forgotten. Multiple agents overwrite each other because they lack a persistent, shared worldview.
> 
> `.kit` is a deterministic, filesystem-anchored memory engine and governance bus for AI. No vector databases. No hallucinations. Just structural integrity.

## 🎯 What does it do?
Instead of probabilistic RAG, `.kit` provides a SQLite-backed **Agent Memory Share Bus (AMSB)** that enforces rules before code is committed.
- **Remember**: `kit learn` injects persistent architectural decisions.
- **Recall**: `kit recall` instantly retrieves $PWD-anchored context.
- **Reflect**: `kit reflect` detects missing knowledge and architectural drift in real-time.
- **Govern**: `kit preflight` (Git hook) strictly blocks agents from committing hallucinated dependencies or violating invariants.

## 🚦 Quickstart

### 1. Install Globally
```bash
# Windows
install.bat

# Linux/macOS
curl -sSL https://raw.githubusercontent.com/vantruong-dang/memory_share/main/install.sh | bash
```

### 2. Initialize a Brain in any repository
```bash
cd your-project
kit init
```

### 3. Teach your agent a physical law
```bash
kit learn --tag invariant "This project strictly uses PostgreSQL. Never use Redis."
```

---

## ⚙️ Command Interface
- **`kit learn`**: Inject explicit decisions or invariants into the ledger.
- **`kit recall`**: Context-anchored, ranked retrieval for the current scope.
- **`kit watch`**: Real-time semantic event stream for background agents.
- **`kit preflight`**: Pre-commit gatekeeper to prevent architectural entropy.
- **`kit doctor`**: Run deterministic self-cleaning and maintenance.

For the low-level Quad-Store schema, FTS5 engine, and the math behind our Supreme Court Arbitrator, see [ARCHITECTURE.md](ARCHITECTURE.md). For the ideological vision, see [MANIFESTO.md](MANIFESTO.md).

---

## ⚖️ License
MIT. Built for the elite AI-native developer.
