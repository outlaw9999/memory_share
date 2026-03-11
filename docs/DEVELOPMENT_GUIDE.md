# `.kit` Development Guide - Implementation Roadmap

**Purpose:** Instructions for developers building V2 components  
**Audience:** Engineers implementing the architecture  
**Version:** 2.0

---

## Project Structure

```
kit/
  __init__.py
  main.py
  
  core/
    grounding.py         # Layer 1: Query grounding
    bridges.py           # Layer 2: Bridge management
    router.py            # Layer 4: Deterministic routing
    distance_cache.py    # Layer 3: Module distance cache
    
  guardian/
    drift_detector.py    # Layer 5: Drift detection
    hotspot_analyzer.py  # Layer 6: Risk analysis
  
  cli/
    commands.py          # kit explain, kit doctor
    
  models/
    grounded_query.py
    cognitive_context.py
    architecture_drift.py
    hotspot.py

runtime/
  kernel.py             # Main execution engine

tests/
  test_grounding.py
  test_bridges.py
  test_router.py
  test_drift_detector.py
  test_hotspot_analyzer.py
  test_integration.py
```

---

## Implementation Sequence (5-6 weeks solo dev)

### Sprint 1: Foundation (Week 1-2)

#### Task 1.1: Query Grounding (2-3 days)
**Deliverable:** `kit/core/grounding.py`

```python
# Code skeleton
class GroundedQuery:
    raw: str
    intent: str
    symbols: List[str]
    confidence: float

def ground_query(query: str, atlas_db: Connection) -> GroundedQuery:
    intent = _classify_intent(query)          # 1ms
    keywords = _extract_keywords(query)       # 1ms
    symbols = _resolve_symbols_fts(keywords)  # 3-5ms
    return GroundedQuery(...)
```

**Tests to write:**
- `test_intent_classification()` - all 4 intents
- `test_keyword_extraction()` - stopword filtering
- `test_symbol_resolution()` - FTS accuracy
- `test_performance()` - must be < 10ms

---

#### Task 1.2: Bridge Schema & Maintenance (2 days)
**Deliverable:** `kit/core/bridges.py` + schema migrations

```python
def create_bridge_tables(atlas_db, memory_db):
    """Create bridges, module_edges tables"""

def update_bridge_statuses(atlas_db, memory_db):
    """Daily job: mark orphans, detect conflicts"""

def auto_bridge_memory(memory_chunk, memory_id, atlas_db, memory_db) -> List[dict]:
    """Generate bridges with confidence scoring"""
```

**Tests:**
- `test_orphan_marking()` - soft orphans work
- `test_bridge_generation()` - confidence 0.6-1.0
- `test_symbol_validation()` - AST checks pass

---

### Sprint 2: Routing & Ranking (Week 2-3)

#### Task 2.1: Distance Cache (3 days)
**Deliverable:** `kit/core/distance_cache.py`

```python
class ModuleDistanceCache:
    def mark_dirty(self):
        """Called when module_edges changes"""
    
    def get_distance(self, module_a: str, module_b: str) -> int:
        """O(1) lookup, lazy recompute on first call"""
    
    def _recompute_all(self):
        """Floyd-Warshall O(n³), ~8ms for 200 modules"""
```

**Tests:**
- `test_initial_compute()` - correctness
- `test_lazy_recompute()` - dirty flag works
- `test_performance()` - O(1) < 2ms after compute

---

#### Task 2.2: Router & Ranker (3-4 days)
**Deliverable:** `kit/core/router.py` + `CognitiveContext`

```python
def route_and_rank(
    grounded_query: GroundedQuery,
    atlas_db, memory_db, distance_cache
) -> CognitiveContext:
    """
    Decision tree:
    - If symbols found: CODE_FIRST flow
    - Else: MEMORY_FIRST fallback
    """

def _search_memory_by_bridge(symbols, atlas_db, memory_db) -> List[dict]:
    """Bridge search + proximity ranking formula"""
```

**Tests:**
- `test_code_first_routing()` - symbols found
- `test_memory_first_fallback()` - no symbols
- `test_ranking_formula()` - weights correct
- `test_performance()` - < 100ms end-to-end

---

### Sprint 3: Guardian Engines (Week 4-5)

#### Task 3.1: Drift Detector (5-7 days)
**Deliverable:** `kit/guardian/drift_detector.py`

```python
def detect_architecture_drift(atlas_db, memory_db) -> List[ArchitectureDrift]:
    """
    Pattern 1: Orphan symbols (1ms)
    Pattern 2: Layer violations (5-10ms)
    Pattern 3: Cycle detection (20-50ms)
    """

def generate_drift_report(drifts) -> str:
    """Pretty formatted report with remediation steps"""
```

**Tests:**
- `test_orphan_detection()` - find real orphans
- `test_layer_violations()` - catch cross-layer imports
- `test_cycle_detection()` - SCCs correct
- `test_report_formatting()` - human readable

---

#### Task 3.2: Hotspot Analyzer (3-4 days)
**Deliverable:** `kit/guardian/hotspot_analyzer.py`

```python
def detect_hotspots(atlas_db, memory_db) -> List[ArchitectureHotspot]:
    """Score modules by fanin/fanout/complexity/docs"""

def generate_hotspot_report(hotspots) -> str:
    """Actionable remediation for each hotspot"""
```

**Tests:**
- `test_risk_scoring()` - formula correct
- `test_threshold_filtering()` - > 0.6 only
- `test_ranking()` - sorted by risk

---

### Sprint 4: CLI & Integration (Week 5-6)

#### Task 4.1: CLI Commands (2 days)
**Deliverable:** `kit/cli/commands.py`

```python
@click.command()
def explain(query: str):
    """kit explain "Why does login fail?" """
    # 1. Ground query
    # 2. Route & rank
    # 3. Format output
    # Performance target: < 100ms

@click.command()
def doctor():
    """kit doctor"""
    # 1. Detect drift (async)
    # 2. Detect hotspots (async)
    # 3. Calculate health score
    # Performance target: < 500ms
```

---

#### Task 4.2: Integration Tests (3-4 days)
**Deliverable:** `tests/test_integration.py`

```python
def test_end_to_end_explain():
    """Full pipeline: grounding → routing → context"""

def test_end_to_end_doctor():
    """Full diagnostic scan"""

def test_performance_targets():
    """< 100ms P95 for explain, < 500ms for doctor"""
```

---

## Critical Implementation Details

### 1. Symbol Ranking Algorithm

```python
def rank_and_select_symbols(keyword: str, fts_results: List[str], atlas_db) -> List[str]:
    """
    Return top-5 symbols by relevance
    
    Scoring:
      exact_match: 1.0
      suffix/prefix: 0.6
      fts_rank: 0.3
    """
    ranked = []
    for symbol in fts_results:
        score = 0.0
        if symbol == keyword:
            score = 1.0
        elif symbol.endswith(f"_{keyword}") or f"_{keyword}_" in symbol:
            score = 0.6
        else:
            score = get_fts_rank(keyword, symbol) * 0.3
        ranked.append((symbol, score))
    
    return [s for s, _ in sorted(ranked, key=lambda x: x[1], reverse=True)[:5]]
```

### 2. Proximity Ranking Formula

```python
proximity_weight = 1.0 / (module_distance + 1)

score = (
    bridge_confidence * 0.4 +
    proximity_weight * 0.3 +
    activation_energy * 0.2 +
    freshness * 0.1
)
```

### 3. Lazy Distance Cache Pattern

```python
class DistanceCache:
    def __init__(self):
        self._cache = {}
        self._dirty = True  # always start dirty
    
    def get(self, a, b):
        if self._dirty:
            self._recompute()  # happens once per session
            self._dirty = False
        return self._cache[(a, b)]
    
    def invalidate(self):
        self._dirty = True
```

### 4. Drift Detection Async Pattern

```python
# In kit explain command
def explain(query):
    # ... route and rank (required) ...
    
    # Optional: lightweight drift check
    light_drifts = detect_light_drifts(...)  # < 10ms
    
    # Full detection happens in `kit doctor` (background)

# In kit doctor command
def doctor():
    # Full comprehensive scan
    drifts = detect_full_drifts(...)  # 100-200ms ok
    hotspots = detect_hotspots(...)
```

---

## Testing Strategy

### Unit Tests (Coverage: 95%+)
- All intent classification cases
- Symbol ranking edge cases
- Distance cache behavior
- Drift pattern detection

### Integration Tests
- Query → context flow
- Bridge creation → orphan marking
- Full doctor scan

### Performance Tests
- Grounding < 10ms
- Router + ranking < 100ms
- Doctor < 500ms

### Property-Based Tests (if using hypothesis)
```python
@given(query=text(min_size=1))
def test_grounding_never_crashes(query):
    result = ground_query(query, atlas_db)
    assert isinstance(result, GroundedQuery)
```

---

## Common Pitfalls & Solutions

### Pitfall 1: False Positive Bridges
**Solution:** Use symbol ranking + AST validation
```python
# WRONG
if "login" in memory_text:
    create_bridge("login")

# RIGHT
symbols = rank_and_select_symbols("login", fts_results)
for symbol in symbols:
    if validate_symbol_context(symbol, memory_text):
        create_bridge(symbol, confidence=0.85)
```

### Pitfall 2: Stale Distance Cache
**Solution:** Dirty flag on dependency change
```python
# Call this whenever module_edges changes
distance_cache.mark_dirty()
```

### Pitfall 3: Drift Detector Timeout
**Solution:** Run as background process
```python
# Kit explain: lightweight only
detect_light_drifts(...) # < 10ms

# Kit doctor: full scan
detect_architecture_drift(...) # ok to take 100-200ms
```

---

## Environment Setup

```bash
# Create virtual env
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"
pip install pytest pytest-benchmark sqlite3

# Run tests
pytest tests/ -v

# Run performance benchmarks
pytest tests/ -v -k benchmark
```

---

## Code Style & Standards

- **PEP 8** for Python
- **Type hints** on all functions
- **Docstrings** for public APIs (Google style)
- **Performance comments** for critical sections
- **sqlite3** for all database access (no ORM)

---

## Deployment Checklist

- [ ] All 6 layers implemented
- [ ] Performance targets met (< 100ms explain)
- [ ] Bridge soft-orphan working
- [ ] Drift detector patterns all passing
- [ ] CLI commands tested
- [ ] Symbol ranking tuned
- [ ] Documentation complete
- [ ] Ready for initial release

---

## Next Document

See **DESIGN_HISTORY.md** for why each architectural decision was made.


---

## [ARCHIVE DATA] V2_IMPLEMENTATION_GUIDE.md

> **Note**: This section contains the original draft content preserved for historical provenance.

# `.kit` V2 Quick Reference for Developers

**Status**: Implementation Ready  
**Target**: 5 Core Layers (25-30 hours estimated effort)  
**Difficulty**: Medium-Hard

---

## QUICK START: What to Build in Order

### 1️⃣ LAYER 1: Query Grounding (Day 1)

**File to create**: `kit/core/grounding.py`

```python
from dataclasses import dataclass
from typing import List

@dataclass
class GroundedQuery:
    raw: str
    intent: str  # "CODE" | "MEMORY" | "DEBUG" | "DECISION"
    symbols: List[str]
    confidence: float

def ground_query(raw_query: str, atlas_db: Connection) -> GroundedQuery:
    intent = classify_intent(raw_query)          # 1ms
    keywords = extract_keywords(raw_query)       # 1ms
    symbols = resolve_symbols_fts(keywords, atlas_db)  # 5ms
    return GroundedQuery(raw_query, intent, symbols, confidence=0.7 if symbols else 0.5)
```

**Tests to write:**
- `test_ground_query_code_intent()`
- `test_ground_query_memory_intent()`
- `test_ground_query_symbol_resolution()`
- `test_ground_query_latency() # Assert < 10ms`

---

### 2️⃣ LAYER 2: Bridge Table (Day 2)

**File to create**: `kit/schema/bridges_schema.sql`

```sql
CREATE TABLE bridges (
    id INTEGER PRIMARY KEY,
    memory_id TEXT UNIQUE,
    symbol_name TEXT,
    relation_type TEXT,  -- 'mentions' | 'applies_to' | 'explains' | 'contradicts'
    confidence REAL,
    status TEXT DEFAULT 'active',  -- 'active' | 'orphan' | 'conflicted'
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_bridges_symbol ON bridges(symbol_name);
CREATE INDEX idx_bridges_status ON bridges(status);
```

**Migration script**: `kit/migrations/003_add_bridges.py`

**Maintenance job**: `kit/services/bridge_maintenance.py`
```python
def daily_bridge_maintenance(atlas_db, memory_db):
    """Mark bridges as orphan when symbols disappear."""
    # Query: UPDATE bridges SET status = 'orphan' WHERE symbol_name NOT IN (SELECT name FROM symbols)
```

**Tests:**
- `test_bridge_table_created()`
- `test_orphan_detection()`
- `test_cascade_not_used()  # Assert bridges survive symbol deletion`

---

### 3️⃣ LAYER 2B: Auto-Bridge Generation (Day 3)

**File to create**: `kit/adapters/bridge_generator.py`

```python
def auto_bridge_memory(memory_chunk: str, memory_id: str, atlas_db, memory_db):
    """Generate bridges with multi-confidence scoring."""
    
    tokens = extract_keywords(memory_chunk)
    bridges = []
    
    for token in tokens:
        candidates = fts_lookup(token, atlas_db, limit=5)
        
        for symbol_name in candidates:
            is_valid = validate_symbol_context(symbol_name, memory_chunk)
            confidence = 0.85 if is_valid else 0.7
            
            bridges.append({
                "memory_id": memory_id,
                "symbol_name": symbol_name,
                "relation_type": "mentions",
                "confidence": confidence
            })
    
    insert_bridges(bridges, memory_db)
    return bridges

def validate_symbol_context(symbol_name: str, memory_chunk: str) -> bool:
    """Check if symbol's module matches memory topic."""
    symbol_module = get_symbol_module(symbol_name)  # "auth"
    memory_mentions = extract_keywords(memory_chunk)  # ["auth", "token", ...]
    return symbol_module.lower() in memory_chunk.lower()
```

**Hook:** Call `auto_bridge_memory()` when `brain_sync_watcher.py` creates new memory chunks.

**Tests:**
- `test_bridge_generation_accuracy() # Assert confidence distribution`
- `test_module_validation()`

---

### 4️⃣ LAYER 3: Module Distance Cache (Day 4)

**File to create**: `kit/core/module_distance.py`

```python
def build_module_distance_cache(atlas_db):
    """Precompute distances between modules."""
    
    modules = get_all_modules(atlas_db)
    cache = {}
    
    for src_module in modules:
        distances = bfs_modules(src_module, atlas_db, max_depth=3)
        cache[src_module] = distances
    
    # Store in SQL
    store_module_distances(atlas_db, cache)

def get_module_distance(symbol_name: str, target_module: str, atlas_db) -> int:
    """O(1) lookup."""
    symbol_module = get_symbol_module(symbol_name, atlas_db)
    
    result = atlas_db.execute(
        "SELECT distance FROM module_distances WHERE module_a = ? AND module_b = ?",
        (symbol_module, target_module)
    )
    return result.fetchone()[0] if result else 99
```

**Refresh strategy:** Call `build_module_distance_cache()` during nightly maintenance.

**Tests:**
- `test_module_cache_accuracy()`
- `test_cache_lookup_latency() # Assert O(1)`

---

### 5️⃣ LAYER 4: Router + Proximity Ranking (Day 5)

**File to update**: `kit/services/cognitive_router.py`

```python
def route_and_rank(grounded_query: GroundedQuery, atlas_db, memory_db):
    if grounded_query.symbols:
        # CODE FIRST
        code_slice = get_code_slice(grounded_query.symbols, atlas_db)
        memory_neurons = search_memory_by_bridge(
            grounded_query.symbols,
            atlas_db,
            memory_db
        )
    else:
        # MEMORY FIRST
        code_slice = {}
        memory_neurons = search_memory_standard(grounded_query.raw, memory_db)
    
    return CognitiveContext(
        query=grounded_query.raw,
        code_slice=code_slice,
        memory_neurons=memory_neurons
    )

def search_memory_by_bridge(symbols: List[str], atlas_db, memory_db) -> List[dict]:
    """Memory search with proximity ranking."""
    
    candidates = memory_db.execute("""
        SELECT m.neuron_id, m.content, b.confidence, b.symbol_name
        FROM bridges b
        JOIN neural_memory m ON b.memory_id = m.id
        WHERE b.symbol_name IN (?, ?, ?)
        AND b.status = 'active'
    """, symbols)
    
    ranked = []
    for neuron_id, content, b_confidence, symbol_name in candidates:
        module_dist = get_module_distance(symbol_name, symbols[0], atlas_db)
        proximity_weight = 1.0 / (module_dist + 1)
        
        score = (b_confidence * 0.4) + (proximity_weight * 0.3)
        ranked.append({
            "neuron_id": neuron_id,
            "score": score,
            "content": content
        })
    
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:10]
```

**Tests:**
- `test_router_code_first()`
- `test_proximity_ranking_accuracy()`
- `test_amnesia_fallback()`

---

### 6️⃣ LAYER 5: Architecture Drift Detector (Day 6)

**File to create**: `kit/analysis/drift_detector.py`

```python
from enum import Enum

class DriftType(Enum):
    ORPHAN_SYMBOL = "orphan"
    LAYER_VIOLATION = "violation"
    TECH_DEBT = "tech_debt"

def detect_drifts(atlas_db, memory_db) -> List[Drift]:
    drifts = []
    
    # Pattern 1: Orphan symbols
    orphans = atlas_db.execute(
        "SELECT symbol_name FROM bridges WHERE status = 'orphan'"
    )
    for (symbol_name,) in orphans:
        drifts.append(Drift(
            type=DriftType.ORPHAN_SYMBOL,
            description=f"Symbol {symbol_name} removed but documented",
            severity="warning"
        ))
    
    # Pattern 2: Layer violations
    # ... check if ui/ imports core/ when documented as isolated
    
    # Pattern 3: Tech debt
    # ... find high-activity modules with minimal documentation
    
    return drifts
```

**Hook:** Call during `kit doctor` command.

**Tests:**
- `test_orphan_detection()`
- `test_layer_violation_detection()`
- `test_drift_reporting()`

---

## DEPENDENCY GRAPH (Build Order)

```
Layer 1: Query Grounding
        ↓
Layer 2: Bridges + Auto-generation
        ↓
Layer 3: Module Distance Cache
        ↓
Layer 4: Router + Ranking
        ↓
Layer 5: Drift Detector
```

**Cannot parallelize:** Layer 1 must finish before Layer 2-4.

---

## Schema Changes Summary

```sql
-- 1. Add bridges table
ALTER TABLE memory_db ADD TABLE bridges (...);

-- 2. Add module_distances cache
ALTER TABLE atlas_db ADD TABLE module_distances (...);

-- 3. Update neural_memory schema (if needed for orphan tracking)
-- None needed, bridges.status handles it
```

---

## Key Files to Modify

| File | Action | Impact |
|------|--------|--------|
| `kit/services/cognitive_router.py` | Replace `fused_query()` logic | **BREAKING CHANGE** → now uses grounding + routing |
| `kit/adapters/memory_adapter.py` | Add bridge search method | Minor addition |
| `brain/ops/brain_sync_watcher.py` | Call `auto_bridge_memory()` on chunk create | Auto-bridge generation |
| `kit/core/kernel.py` | Add `ground_query()` call | New grounding layer |
| (new) `kit/core/grounding.py` | Create | Query grounding logic |
| (new) `kit/services/bridge_maintenance.py` | Create | Bridge orphan detection |
| (new) `kit/analysis/drift_detector.py` | Create | Drift analysis |

---

## Test Coverage Plan

**Total tests needed:** ~25-30 unit tests

- Grounding: 4 tests
- Bridges: 4 tests
- Auto-bridge: 3 tests
- Module cache: 3 tests
- Router: 4 tests
- Ranking: 3 tests
- Drift detection: 4 tests

**Run all**: `pytest tests/test_kit_v2.py -v`

---

## Latency Acceptance Criteria

```
Grounding:           < 10ms ✅
Code slice:          < 20ms ✅
Bridge search:       < 15ms ✅
Drift detection:     < 50ms (async) ✅
━━━━━━━━━━━━━━━━━━━━━━━
Total P95:           <100ms ✅
```

---

## Deployment Steps

1. Create schema migration (bridges + module_distances)
2. Deploy Layer 1 (grounding) — no breaking changes yet
3. Deploy Layer 2 (bridges) — add bridge table, populate via migration
4. Deploy Layer 2B (auto-bridge) — hook into brain_sync_watcher
5. Build Layer 3 cache — batch job on first run
6. Deploy Layer 4 (new router) — **BREAKING CHANGE**, requires testing
7. Deploy Layer 5 (drift detector) — hook into `kit doctor`

**Rollback strategy**: Keep old `fused_query()` available for 1 week, route via feature flag.

---

## Success Signals

- ✅ `kit explain "Why does login fail?"` completes < 100ms
- ✅ Memory results rank by proximity (module distance matters)
- ✅ Drift report accurately identifies orphans and violations
- ✅ Bridges survive code refactors (no cascading deletes)
- ✅ No more query type mismatch errors

---

**Ready to start coding?** Begin with Layer 1: `kit/core/grounding.py` 🚀
