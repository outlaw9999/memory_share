# .kit Deployment Verification Checklist

**Use this before staging deployment — verify everything works!**

---

## Pre-Deployment Verification (30 minutes)

### Step 1: File Integrity Check (5 min)

```bash
# Verify all core files exist
[ -f "runtime/graph_slice_engine.py" ] && echo "✅ graph_slice_engine.py" || echo "❌ MISSING"
[ -f "runtime/architecture_watchdog.py" ] && echo "✅ architecture_watchdog.py" || echo "❌ MISSING"
[ -f "plugins/atlas_indexer/incremental_updater.py" ] && echo "✅ incremental_updater.py" || echo "❌ MISSING"

# Verify documentation exists
[ -f "ARCHITECTURE_GRAPH_SLICE_INCREMENTAL.md" ] && echo "✅ Architecture Guide" || echo "❌ MISSING"
[ -f "ARCHITECTURE_WATCHDOG_GUIDE.md" ] && echo "✅ Watchdog Guide" || echo "❌ MISSING"
[ -f "KIT_COMPLETE_SYSTEM.md" ] && echo "✅ Complete System Guide" || echo "❌ MISSING"
[ -f "KIT_QUICK_REFERENCE.md" ] && echo "✅ Quick Reference" || echo "❌ MISSING"

# Expected output: All ✅
```

### Step 2: Dependencies Check (5 min)

```bash
# Install requirements
pip install -r requirements.txt

# Verify imports work
python3 << 'EOF'
try:
    from runtime.graph_slice_engine import GraphSliceEngine
    print("✅ GraphSliceEngine imports")
except Exception as e:
    print("❌ GraphSliceEngine import failed:", e)

try:
    from runtime.architecture_watchdog import ArchitectureWatchdog
    print("✅ ArchitectureWatchdog imports")
except Exception as e:
    print("❌ ArchitectureWatchdog import failed:", e)

try:
    from plugins.atlas_indexer.incremental_updater import IncrementalUpdater
    print("✅ IncrementalUpdater imports")
except Exception as e:
    print("❌ IncrementalUpdater import failed:", e)

import sqlite3
print("✅ sqlite3 available")
EOF

# Expected: All ✅
```

### Step 3: Database Setup (5 min)

```bash
# Check if atlas.db exists from previous indexing
if [ -f "atlas.db" ]; then
    echo "✅ atlas.db found"
    
    # Verify schema
    echo "Checking schema..."
    sqlite3 atlas.db "SELECT name FROM sqlite_master WHERE type='table';" | grep -q "symbols"
    [ $? -eq 0 ] && echo "✅ Schema valid" || echo "⚠️  Run indexer first"
else
    echo "⚠️  atlas.db not found — you need to index your codebase first"
    echo "   Run: python plugins/atlas_indexer/tailer.py"
fi
```

### Step 4: Unit Tests (10 min)

```bash
# Run unit tests
echo "Running Graph Slice tests..."
pytest test_graph_slice_and_incremental.py::TestGraphSliceEngine -v

echo "Running Incremental Updater tests..."
pytest test_graph_slice_and_incremental.py::TestIncrementalUpdater -v

echo "Running Watchdog tests..."
pytest test_architecture_watchdog.py::TestArchitectureWatchdog -v

# Expected: All passing
```

### Step 5: Integration Test (5 min)

```bash
echo "Running integration test..."
pytest test_graph_slice_integration_benchmark.py::TestIntegrationPipeline -v

# Should confirm: <100ms latency, correct slice format
```

### Step 6: Performance Validation (5 min)

```bash
echo "Validating latency targets..."
python test_graph_slice_integration_benchmark.py

# Expected output should show:
# - Slice time: 5-20ms per query
# - Watchdog scan: <100ms
# - Memory: <500MB
```

---

## Verification Checklist

```
PRE-DEPLOYMENT VERIFICATION
==========================

Core Files:
  ☐ runtime/graph_slice_engine.py exists
  ☐ runtime/architecture_watchdog.py exists
  ☐ plugins/atlas_indexer/incremental_updater.py exists
  ☐ plugins/atlas_indexer/indexer.py modified with incremental support

Tests:
  ☐ test_graph_slice_and_incremental.py exists
  ☐ test_graph_slice_integration_benchmark.py exists
  ☐ test_architecture_watchdog.py exists

Documentation:
  ☐ ARCHITECTURE_GRAPH_SLICE_INCREMENTAL.md exists
  ☐ ARCHITECTURE_WATCHDOG_GUIDE.md exists
  ☐ KIT_COMPLETE_SYSTEM.md exists
  ☐ KIT_QUICK_REFERENCE.md exists
  ☐ QUICKSTART_GRAPH_SLICE.py exists

Dependencies:
  ☐ pip install -r requirements.txt succeeds
  ☐ GraphSliceEngine imports without error
  ☐ ArchitectureWatchdog imports without error
  ☐ IncrementalUpdater imports without error
  ☐ sqlite3 available

Database:
  ☐ atlas.db exists
  ☐ Schema verified (tables: symbols, calls, applied_txns)
  ☐ Indexed at least 1000 symbols

Unit Tests:
  ☐ TestGraphSliceEngine passes (all 5+ tests)
  ☐ TestIncrementalUpdater passes (all 4+ tests)
  ☐ TestArchitectureWatchdog passes (all 5+ tests)

Integration Tests:
  ☐ TestIntegrationPipeline passes
  ☐ Confirmed slice output is valid JSON
  ☐ Confirmed watchdog output is valid JSON

Performance:
  ☐ Slice latency < 20ms
  ☐ Watchdog latency < 100ms
  ☐ Memory usage < 500MB
  ☐ Token reduction > 100x validated

OVERALL: Ready for staging? ☐ YES / ☐ NOT YET
```

---

## First-Run Commands (Verify Each Works)

### Test 1: Extract a Slice

```bash
python3 << 'EOF'
from runtime.graph_slice_engine import GraphSliceEngine

engine = GraphSliceEngine("atlas.db")

# Choose any symbol from your codebase
# Example: "UserService.login" or "main" or whatever exists
try:
    result = engine.slice("main", depth=2)  # Replace "main" with a real symbol
    
    if 'token_estimate' in result:
        print(f"✅ Slice works!")
        print(f"   Tokens: {result['token_estimate']}")
        print(f"   Nodes: {len(result.get('nodes', []))}")
    else:
        print("⚠️  Slice returned but missing expected fields")
        print(f"   Result: {result}")
except Exception as e:
    print(f"❌ Slice failed: {e}")
EOF
```

**Expected output**: `✅ Slice works! Tokens: 200-500 Nodes: 10-50`

### Test 2: Scan for Violations

```bash
python3 << 'EOF'
from runtime.architecture_watchdog import ArchitectureWatchdog
import json

watchdog = ArchitectureWatchdog("atlas.db")

# Scan a sample file
try:
    violations = watchdog.scan_changes(["any_file.py"])  # Replace with real file
    
    print(f"✅ Watchdog scan works!")
    print(f"   Violations found: {len(violations)}")
    
    if violations:
        print(f"   Types: {set(v.type for v in violations)}")
        print("\n   Sample violation:")
        print(f"   - Type: {violations[0].type}")
        print(f"   - Severity: {violations[0].severity}")
        print(f"   - File: {violations[0].file}")
except Exception as e:
    print(f"❌ Watchdog scan failed: {e}")
EOF
```

**Expected output**: `✅ Watchdog scan works! Violations found: 0-5`

### Test 3: Check Incremental Update

```bash
python3 << 'EOF'
from plugins.atlas_indexer.incremental_updater import IncrementalUpdater
import time

updater = IncrementalUpdater("atlas.db")

try:
    start = time.time()
    
    # Simulate a file update (no actual changes)
    updater.update_file_delta(
        "test_file.py",
        new_symbols=[],
        new_edges=[]
    )
    
    elapsed = time.time() - start
    print(f"✅ Incremental update works!")
    print(f"   Latency: {elapsed*1000:.1f}ms (target: <50ms)")
    
    if elapsed < 0.05:
        print(f"   ✅ Latency target MET")
    else:
        print(f"   ⚠️  Latency exceeded target")
except Exception as e:
    print(f"❌ Incremental update failed: {e}")
EOF
```

**Expected output**: `✅ Incremental update works! Latency: 30-50ms ✅ Latency target MET`

---

## Staging Deployment Checklist

Once all above checks pass:

```
STAGING DEPLOYMENT
==================

Environment Setup:
  ☐ Create staging environment (separate from production)
  ☐ Copy .kit files to staging
  ☐ Copy atlas.db from production
  ☐ Create architecture.json with your layer structure

Testing on Staging:
  ☐ Run all tests: pytest test_*.py -v (all pass)
  ☐ Create test PR with intentional violation
  ☐ Verify GitHub Actions detects it
  ☐ Verify pre-commit hook blocks it
  ☐ Test: Fix violation, verify it passes

Policy Configuration:
  ☐ Review architecture.json
  ☐ Define your layer structure
  ☐ Set violation severities (ERROR vs WARNING vs INFO)
  ☐ Define thresholds (god_module, cyclomatic, etc.)
  ☐ Add exceptions for legacy code (with expiration dates)

CI/CD Integration:
  ☐ Create .github/workflows/architecture-check.yml
  ☐ Test workflow on sample PR
  ☐ Verify workflow comments with findings
  ☐ Populate CHANGED_FILES in workflow correctly

Team Communication:
  ☐ Announce staging to team
  ☐ Share KIT_QUICK_REFERENCE.md
  ☐ Schedule walkthrough on policy
  ☐ Explain workflow: blocking → fixing → merge

Monitoring (Week 1-2):
  ☐ Review violations found
  ☐ Track false positive rate
  ☐ Document common violation types  
  ☐ Adjust policy thresholds as needed
  ☐ Get team feedback

Production Promotion:
  ☐ False positive rate < 5%
  ☐ Team trained on remediation
  ☐ Policy refined and stable
  ☐ Documentation complete
  ☐ Ready: Enable blocking mode
```

---

## Troubleshooting Quick Fixes

### "ImportError: No module named 'runtime'"

```bash
# Verify Python path includes current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Retry test
python test_graph_slice_and_incremental.py
```

### "sqlite3.OperationalError: no such table: symbols"

```bash
# Database not initialized — run indexer first
echo "Run indexer to create schema:"
python plugins/atlas_indexer/tailer.py

# Or restore from production
cp /production/atlas.db ./atlas.db
```

### "Watchdog returns no violations (all tests skip)"

```bash
# Graph likely empty — check indexed symbols
sqlite3 atlas.db "SELECT COUNT(*) FROM symbols;"

# Should show > 100 symbols
# If 0: run indexer first
```

### "Slice returns empty nodes list"

```bash
# Symbol doesn't exist in DB — verify it's indexed
symbol_name="MyClass.method"  # Change to real symbol

sqlite3 atlas.db \
  "SELECT * FROM symbols WHERE name LIKE '%${symbol_name}%' LIMIT 5;"

# If no results: need different symbol name
```

### "Policy configuration not working"

```bash
# Verify architecture.json exists and is valid JSON
python3 -c "import json; json.load(open('architecture.json'))"

# Should succeed silently
# If error: fix JSON syntax
```

---

## Success Indicators

After running all checks, you should see:

```
✅ All files present
✅ All imports working
✅ Database schema valid
✅ All unit tests passing (15+)
✅ Integration tests passing (5+)
✅ Slice latency < 20ms
✅ Watchdog latency < 100ms
✅ Memory < 500MB
✅ Token reduction > 100x

Status: READY FOR STAGING ✅
```

---

## Sign-Off for Staging

**Once all checkboxes are ticked:**

```
PROJECT: .kit Code Intelligence Engine
VERSION: 1.0
STATUS: Ready for Staging Deployment

VERIFIED BY: ___________________
DATE: ___________________
TIME: ___________________

SIGN-OFF: ✅ READY
```

---

## What Happens at Staging

**Week 1**: Warning mode
- Watchdog detects violations
- Comments on PRs but doesn't block
- Collect metrics, observe patterns

**Week 2**: Adjustment phase
- Review violations detected
- Update policy if needed
- Train team on fixes
- Reduce false positives

**Week 3**: Enforcement mode
- Enable error-level blocking
- Pre-commit hooks active
- Deploy to all machines
- Monitor merge blocks

**Week 4+**: Production stability
- Metrics show <5% false positives
- Team familiar with remediations
- Policy stable and documented
- Ready for permanent deployment

---

## Questions?

See:
- **"Why did it fail?"** → Fix section above
- **"How does it work?"** → `ARCHITECTURE_GRAPH_SLICE_INCREMENTAL.md`
- **"How do I use it?"** → `KIT_QUICK_REFERENCE.md`
- **"I need to customize"** → `ARCHITECTURE_WATCHDOG_GUIDE.md`

---

**Ready to proceed?** → Follow checklist above, get all ✅, then deploy!

🚀
