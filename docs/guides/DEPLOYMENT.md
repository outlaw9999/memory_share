# .kit Deployment & Verification Guide

This guide covers the verification checklist, staging deployment steps, and quick reference for `.kit` operators.

---

## 🛡️ Pre-Deployment Verification (30 minutes)

Run these checks before promoting to staging or production to ensure system integrity.

### 1. File & Dependency Check
```bash
# Verify core components
ls kit/graph_slice_engine.py kit/indexer.py kit/incremental_updater.py

# Install dependencies
pip install -r requirements.txt
```

### 2. Unit & Integration Tests
```bash
# Run core test suite
pytest tests/ -v

# Validate latency & compression targets
python tests/test_graph_slice_integration_benchmark.py
```

### 3. Database Initialization
```bash
# Initialize and index the repository
kit init
kit index
```

---

## 🚀 Staging Deployment Checklist

Once local verification passes, follow these steps for staging:

1. **Environment Setup**: Copy `.kit` runtime to a separate staging environment.
2. **Policy Configuration**: Create `architecture.json` reflecting your project's layer structure.
3. **Dry-Run Monitoring**: Deploy the Watchdog in "warning mode" for 1 week to observe violation patterns.
4. **Validation**: Create a test PR with an intentional violation to verify CI/CD blocking works.
5. **Team Training**: Share the Quick Reference below with the engineering team.

---

## ⚡ Quick Reference Card

### Core API Usage

**Extract a Slice (for Agents)**:
```python
from kit.graph_slice_engine import GraphSliceEngine
engine = GraphSliceEngine("atlas.db")
slice = engine.slice("MyClass.method", depth=2)
# Result: <500 tokens of semantic context
```

**Architecture Watchdog**:
```python
from kit.architecture_watchdog import ArchitectureWatchdog
watchdog = ArchitectureWatchdog("atlas.db")
violations = watchdog.scan_changes(["app/service.py"])
if watchdog.should_block_merge():
    print(watchdog.format_report())
```

### Common CLI Commands
| Command | Purpose |
|---------|---------|
| `kit index` | Update code graph (Incremental) |
| `kit doctor` | Full health & architecture check |
| `kit symbol <q>` | Search unified symbols |
| `kit query impact` | Blast radius analysis |

---

## 🛠️ Troubleshooting

- **Import Errors**: Ensure your `PYTHONPATH` includes the repository root.
- **Empty Slices**: Verify the symbol exists in the graph using `kit symbol <name>`.
- **High Latency**: Check if `atlas.db` is on a slow filesystem; SQLite performs best on local SSDs.
