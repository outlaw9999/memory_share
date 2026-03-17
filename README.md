# .kit — Deterministic Memory for AI Agents

> .kit is a deterministic memory engine for AI agents, with a built-in governance and coordination layer.

## 🚨 The Problem: Agents Have No Memory
Current AI agents suffer from a fatal flaw: **They are stateless.** Context windows reset after every interaction. Architectural decisions are forgotten. Multiple agents working on the same repository overwrite each other's logic because they do not share a persistent, deterministic worldview.

## 💡 The Solution

`.kit` is a deterministic memory engine for AI agents.

It acts as a cognitive infrastructure layer, enabling shared memory, coordination, and governance across multiple agents—anchored directly to your filesystem.

---

## 🎯 Who is this for?

- AI-native developers
- Multi-agent systems
- Teams using Codex, Google Antigravity, or other automation agents


## 🏛️ Architecture: The 7-Layer Cognitive Map

.kit is built on a modular hierarchy, evolving from raw storage to active cognition:

### Layers 1–4: The Memory Engine (SAM Core)
1. **Persistence Layer**: SQLite FTS5 - Fast, deterministic, zero-infrastructure storage.
2. **Contextual Layer**: Hierarchy-based recall anchored to your `$PWD`.
3. **Temporal Layer**: Immutable Ledger - Append-only history with full time-travel capability.
4. **Ranking Layer**: `materialized_score` - Deterministic ranking based on Importance, Frequency, and Decay (No runtime AI math).

### Layers 5–6: The Cognitive Bus (AMSB)
5. **Coordination Layer**: Multi-agent shared memory space with event-driven updates.
6. **Governance Layer**: `kit preflight` - Architectural gatekeeper (Git Hook) that enforces discipline and blocks hallucinations.

### Layer 7: Cognitive Feedback (Coming Soon)
7. **Feedback Layer**: `kit reflect` - Self-awareness, Gap Detection, and Architectural Drift analysis.

---

## 🚦 Getting Started

### 1. Installation
```bash
# Windows
install.bat

# Linux/macOS
curl -sSL https://raw.githubusercontent.com/vantruong-dang/memory_share/main/install.sh | bash
```

### 2. Initialize your Brain
```bash
cd my-project
kit init
```
This bootstraps `.kit/brain.db` and the canonical `AGENTS.md` manifest.

---

## ⚙️ Command Interface
- **`kit learn`**: Inject explicit decisions or invariants into the ledger.
- **`kit recall`**: Context-anchored, ranked retrieval for the current scope.
- **`kit watch`**: Real-time semantic event stream for background agents.
- **`kit preflight`**: Pre-commit gatekeeper to prevent architectural entropy.
- **`kit doctor`**: Run deterministic self-cleaning and maintenance.

---

## 📜 Technical Deep Dive
For detailed information on the Quad-Store schema, FTS5 indexing, and the cognitive ranking algorithm, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## ⚖️ License
MIT. Built for the elite AI-native developer.
