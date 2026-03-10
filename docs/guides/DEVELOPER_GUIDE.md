# Developer Guide — Getting Started with .kit

**What You'll Learn**: How to use `.kit` in your own code and integrate it into your development workflow.

---

## 30-Second Overview

`.kit` = Code Intelligence Engine for large monorepos

**What it does**:
- Extract semantic slices of code (200-token context from 50M LOC)
- Detect architecture violations automatically
- Analyze real-time code changes (<50ms updates)

**Who it's for**:
- Developers who want context-aware code analysis
- Architects enforcing design patterns
- DevOps engineers building code quality gates

---

## Installation (5 minutes)

### 1. Clone Repository

```bash
git clone https://github.com/outlaw9999/memory_share
cd memory_share
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
python3 << 'EOF'
from runtime.graph_slice_engine import GraphSliceEngine
from runtime.architecture_watchdog import ArchitectureWatchdog
print("✅ Installation successful!")
EOF
```

---

## Core APIs

### 1. Graph Slice Engine — Get Code Context

**Purpose**: Extract a minimal semantic neighborhood around a code symbol.

```python
from runtime.graph_slice_engine import GraphSliceEngine

# Initialize
engine = GraphSliceEngine("atlas.db")

# Get a slice for a symbol
result = engine.slice("AuthService.login", depth=2, max_nodes=50)

# Result contains:
# - symbol: target symbol
# - callers: who calls this
# - callees: what this calls
# - token_estimate: approx LLM tokens
# - nodes: list of related symbols
```

**Use Case 1**: Agent Context

```python
# User asks: "Help me understand AuthService.login()"
# Code: 
engine = GraphSliceEngine("atlas.db")
slice = engine.slice("AuthService.login", depth=2, max_nodes=30)

# Send to LLM with <200 tokens
prompt = f"Here's the code context:\n{json.dumps(slice)}\n\nQuestion: ..."
response = llm.ask(prompt)
```

**Use Case 2**: Code Review

```python
# When reviewing a PR that modifies auth/service.py
# Show what might break:
changed_symbols = extract_changes("auth/service.py")

for symbol in changed_symbols:
    impact = engine.slice(symbol, depth=3, max_nodes=100)
    print(f"If {symbol} changes, these are affected:")
    for caller in impact['callers']:
        print(f"  - {caller}")
```

**Use Case 3**: Navigation

```python
# User: "What other functions use TokenService.issue?"
# Code:
slice = engine.slice("TokenService.issue", depth=1)
for caller in slice['callers']:
    print(caller)
```

### 2. Architecture Watchdog — Detect Violations

**Purpose**: Find architectural violations automatically.

```python
from runtime.architecture_watchdog import ArchitectureWatchdog, ArchitecturePolicy

# Define policy
policy = ArchitecturePolicy(
    layers=["api", "service", "repo", "util"],
    allowed_transitions={
        "api": ["service", "repo", "util"],
        "service": ["repo", "util"],
        "repo": ["util"],
        "util": []
    },
    max_fanout=10,
    max_god_module_size=1000
)

# Initialize
watchdog = ArchitectureWatchdog("atlas.db", policy)

# Scan for violations
violations = watchdog.scan_changes(["auth/service.py", "api/users.py"])

if violations:
    print(watchdog.format_report())
    
    # Should we block the merge?
    if watchdog.should_block_merge():
        print("❌ Merge blocked — critical violations detected")
        exit(1)
    else:
        print("⚠️  Warnings detected, but merge allowed")
```

### 3. Incremental Updater — Real-Time Graph Updates

**Purpose**: Update the graph when files change (30-50ms, not 5-30s).

```python
from plugins.atlas_indexer.incremental_updater import IncrementalUpdater

# Initialize
updater = IncrementalUpdater("atlas.db")

# When a file changes, update the graph
new_symbols = parse_file("auth/service.py")
result = updater.update_file_delta("auth/service.py", new_symbols)

print(f"Updated in {result.execution_time_ms}ms")
print(f"Added: {len(result.added_symbols)} symbols")
print(f"Changed: {len(result.modified_symbols)} symbols")
```

---

## Complete Workflow Example

```python
import json
from runtime.graph_slice_engine import GraphSliceEngine
from runtime.architecture_watchdog import ArchitectureWatchdog, ArchitecturePolicy

# 1. Initialize
engine = GraphSliceEngine("atlas.db")

policy = ArchitecturePolicy(
    layers=["api", "service", "repo", "util"],
    allowed_transitions={
        "api": ["service", "repo", "util"],
        "service": ["repo", "util"],
        "repo": ["util"],
        "util": []
    }
)
watchdog = ArchitectureWatchdog("atlas.db", policy)

# 2. Get context for a symbol
print("📚 Getting code context...")
context = engine.slice("UserService.authenticate", depth=2)
print(f"Found {context['slice_size']} related symbols")
print(f"Token estimate: {context['token_estimate']}")

# 3. Check for violations
print("🚨 Checking architecture...")
violations = watchdog.scan_changes(["service/user.py"])
if violations:
    print(watchdog.format_report())
else:
    print("✅ No violations detected")

# 4. Show impact of changes
print("💥 Impact analysis...")
for caller in context['callers']:
    print(f"  Changing will affect: {caller}")

# 5. Make a decision
print("✅ Ready to proceed with changes")
```

---

## Configuration

### Policy Configuration

Create `.kit/architecture.json`:

```json
{
  "layers": ["api", "service", "repo", "util"],
  "allowed_transitions": {
    "api": ["service", "repo", "util"],
    "service": ["repo", "util"],
    "repo": ["util"],
    "util": []
  },
  "max_fanout": 10,
  "max_god_module_size": 1000,
  "exempt_paths": ["test", "mock", "example"]
}
```

### Slice Configuration

```python
# Default: small slices for agent context
small = engine.slice("Symbol", depth=1, max_nodes=20)

# For impact analysis: larger slices
large = engine.slice("Symbol", depth=3, max_nodes=100)

# Custom configuration
custom = engine.slice(
    "Symbol",
    depth=2,
    max_nodes=50,
    centrality_weight=0.6,  # Favor central nodes
    call_freq_weight=0.3
)
```

---

## Integration Patterns

### With LLM Agents

```python
# Pattern: Get context → Ask LLM → Get answer
engine = GraphSliceEngine("atlas.db")

def answer_code_question(question: str, symbol: str) -> str:
    # 1. Get code context
    context = engine.slice(symbol, depth=2, max_nodes=30)
    
    # 2. Build prompt
    prompt = f"""
    Question: {question}
    
    Code context (from symbol {symbol}):
    {json.dumps(context, indent=2)}
    
    Answer based on the above code context.
    """
    
    # 3. Ask LLM
    response = llm.ask(prompt)
    
    return response

# Usage
answer = answer_code_question(
    "What happens when login() is called with invalid credentials?",
    "AuthService.login"
)
```

### With CI/CD Pipeline

```bash
#!/bin/bash
# check-architecture.sh

python3 << 'EOF'
from runtime.architecture_watchdog import ArchitectureWatchdog, ArchitecturePolicy
import sys

policy = ArchitecturePolicy(
    layers=["api", "service", "repo", "util"],
    allowed_transitions={"api": ["service", "repo", "util"], ...}
)

watchdog = ArchitectureWatchdog("atlas.db", policy)
violations = watchdog.scan_changes()

if watchdog.should_block_merge():
    print("❌ Architecture check failed")
    sys.exit(1)
else:
    print("✅ Architecture check passed")
    sys.exit(0)
EOF
```

### With Code Review Tools

```python
# Integrate with code review bot
def review_pull_request(pr_files: List[str]) -> ReviewResult:
    engine = GraphSliceEngine("atlas.db")
    watchdog = ArchitectureWatchdog("atlas.db", policy)
    
    # 1. Check for violations
    violations = watchdog.scan_changes(pr_files)
    
    # 2. Get impact analysis
    impact = []
    for file in pr_files:
        for symbol in extract_symbols(file):
            slice = engine.slice(symbol, depth=2)
            impact.append({
                "symbol": symbol,
                "affected_by": slice['callers']
            })
    
    # 3. Return review
    return ReviewResult(violations, impact)
```

---

## Common Tasks

### Task 1: Find What Will Break When I Change This?

```python
engine = GraphSliceEngine("atlas.db")

# Get all functions that call this
symbol = "DatabaseService.query"
context = engine.slice(symbol, depth=1)

print(f"Changing {symbol} will affect:")
for caller in context['callers']:
    print(f"  - {caller}")
```

### Task 2: Check If My Code Follows Architecture

```python
watchdog = ArchitectureWatchdog("atlas.db", policy)

# Scan the file you're working on
violations = watchdog.scan_changes(["service/my_service.py"])

if violations:
    print("Architecture violations found:")
    print(watchdog.format_report())
else:
    print("✅ Your code follows the architecture")
```

### Task 3: Understanding a Module

```python
engine = GraphSliceEngine("atlas.db")

# Get a large slice for detailed understanding
slice = engine.slice("MyModule.main_function", depth=3, max_nodes=100)

print(f"This module contains {slice['slice_size']} related functions")
print(f"It is called by: {slice['callers']}")
print(f"It calls: {slice['callees']}")
```

### Task 4: Finding Dead Code

```python
watchdog = ArchitectureWatchdog("atlas.db")

# Watchdog can identify symbols with no callers
dead_code = watchdog.find_dead_code()

for symbol in dead_code:
    print(f"Dead code: {symbol} (never called)")
    
    # Can my remove safely?
    print(f"  Safe to remove: {symbol.is_safe_to_remove()}")
```

---

## Testing

### Unit Test Your Integration

```python
import pytest
from runtime.graph_slice_engine import GraphSliceEngine

def test_slice_returns_valid_format():
    engine = GraphSliceEngine("atlas.db")
    result = engine.slice("TestSymbol", depth=1)
    
    assert "symbol" in result
    assert "slice_size" in result
    assert "token_estimate" in result
    assert result["slice_size"] <= 50

def test_watchdog_finds_violations():
    watchdog = ArchitectureWatchdog("atlas.db", policy)
    violations = watchdog.scan_changes(["test_file.py"])
    
    assert isinstance(violations, list)

# Run tests
pytest test_my_integration.py -v
```

---

## Troubleshooting

### Q: Graph seems stale or missing recently-added symbols

**A**: The graph index is out of sync.

```bash
# Reindex the repository
python plugins/atlas_indexer/tailer.py

# Or incrementally update
python plugins/atlas_indexer/incremental_updater.py
```

### Q: Slice is too small (missing important context)

**A**: Increase depth or max_nodes:

```python
# Try larger slice
large_slice = engine.slice("Symbol", depth=3, max_nodes=100)

# Check token estimate
print(f"Tokens: {large_slice['token_estimate']}")
```

### Q: Getting false positives in architecture check

**A**: Adjust policy or mark exceptions:

```python
# Update .kit/architecture.json
policy = {
    ...
    "exempt_paths": ["test", "mock", "legacy"]  # Add exceptions
}
```

### Q: Can't import modules

**A**: Verify installation:

```bash
pip install -r requirements.txt
python -c "from runtime.graph_slice_engine import GraphSliceEngine; print('OK')"
```

---

## Advanced Topics

### Custom Symbolic Weighting

```python
# Customize how symbols are ranked in slices
engine = GraphSliceEngine("atlas.db")

config = {
    "centrality_weight": 0.7,      # Prefer central nodes
    "call_freq_weight": 0.2,       # Less weight to frequency
    "boundary_penalty": 0.1        # Prefer internal calls
}

slice = engine.slice("Symbol", config=config)
```

### Analyzing Temporal Patterns

```python
# Understanding how symbols are changing
engine = GraphSliceEngine("atlas.db")

# Compare two versions
old_slice = engine.slice("Symbol", version="v1.0")
new_slice = engine.slice("Symbol", version="v1.1")

print(f"Added calls: {set(new_slice['callees']) - set(old_slice['callees'])}")
print(f"Removed calls: {set(old_slice['callees']) - set(new_slice['callees'])}")
```

---

## Resources

- [Complete Architecture Overview](../ARCHITECTURE.md)
- [Technical Deep-Dive: Graph Slice & Indexing](../engines/GRAPH_AND_INDEXING.md)
- [Deployment Guide](DEPLOYMENT.md)
- [API Reference](#) (coming soon)

---

**Next Step**: [Deploy to your repository →](./DEPLOYMENT.md)
