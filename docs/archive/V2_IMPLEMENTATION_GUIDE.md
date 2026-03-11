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
