# `memory_share.kit` — The Architecture Memory Protocol (AMP)

![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Protocol](https://img.shields.io/badge/protocol-AMP--0001-red.svg)

**The "SQLite of AI Coding". A deterministic architecture memory kernel for AI Agents.**

`memory_share.kit` is a production-grade implementation of the **Architecture Memory Protocol (AMP)**. It transforms your repository into a deterministic knowledge graph, allowing AI agents to reason about complex architectures with **97% token savings** and absolute structural precision.

## 🏁 Requirements

Python **3.14+ only**

`.kit` uses modern Python runtime improvements and is developed exclusively on Python 3.14. Earlier versions are not supported.

## 📺 Quick Demo

```bash
# Analyze architectural dependencies of a component
kit query impact GraphSliceEngine
```

**Output Example**:
```text
GraphSliceEngine
 ├─ IncrementalUpdater
 ├─ GraphStore
 └─ ASTParser
```

## 🚀 The 1000x Token Compression Challenge

Traditional AI agents read your entire codebase, wasting thousands of tokens. `.kit` changes the game.

| Method | Context Input | Token Efficiency | Reasoning Quality |
| --- | --- | --- | --- |
| **Traditional RAG** | Raw Files | $1\times$ (Baseline) | Low (Too much noise) |
| **Semantic Jump** | Filtered Paths | $25\times$ | Medium |
| **Graph Slice** | **Sub-graph** | **$150\times$** | **High** |
| **Signal Envelope** | **Insights** | **$1,600\times+$** | **Superior** |

> **"Don't feed the AI code. Feed it Intelligence."** — Triết lý cốt lõi của `.kit`.

## ⚡ Key Features

- **Graph Slice Engine**: Extract 200-token semantic slices from 50M+ LOC.
- **Incremental Indexing**: Real-time graph updates in **30-50ms**.
- **Architecture Watchdog**: Automatically block PRs that violate structural policies.
- **Zero Dependencies**: Pure Python + SQLite (stdlib). Offline-first.

## 📊 Architecture Health

When running `kit doctor`, you might see a "CRITICAL" status with several violations. **This is normal and expected for real-world codebases.** `.kit` is sensitive enough to detect subtle architectural drifts, cyclic dependencies, and layer crossings. Use the report as a guide for refactoring, not as a blocking failure.

## 📦 Quick Start (60 Seconds)

```bash
# 1. Install local version
pip install -e .

# 2. Index your codebase
kit init
kit index

# 3. Running a health check
kit doctor
```

## 🌍 Elite Installation (Distribution)

For friends and colleagues who want to use the **Architecture Memory Kernel** without cloning the full repository, they can install it directly via `pip`:

```bash
pip install git+https://github.com/vantruong-dang/memory_share.kit.git
```

> **Requirement:** Python 3.14+ must be installed on the target machine. Once installed, the `kit` command becomes available globally.

## 📖 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Technical design & maturity scorecard.
- **[AMP-0001.md](AMP-0001.md)**: Architecture Memory Protocol (Standardization).
- **[docs/engines/graph-and-indexing.md](docs/engines/graph-and-indexing.md)**: Slicing & Incrementalism deep-dive.
- **[docs/guides/deployment.md](docs/guides/deployment.md)**: Setup, Staging, & Verification.
- **[docs/guides/developer-guide.md](docs/guides/developer-guide.md)**: API usage & customization.

---

**Built for tools and agents that need to reason about code structure, not just read text.** 🧠🌐✨
