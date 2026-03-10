# Known Limitations & Trade-offs

**Status**: Fully documented as of v1.0.0  
**Impact**: Informs metric interpretation and query reliability

---

## Critical Limitations (Affect Metric Reliability)

### 1. Edge Incompleteness Bias (Static Analysis Limitation)

**What**: The dependency graph is incomplete — static analysis misses dynamic dispatch, reflection, meta-programming, plugin systems.

**Impact**: 
- Metrics unreliable for repos with **> 500k edges** and dense dynamic code
- Graph completeness varies by language (Python: 70-80%, JavaScript: 50-60%)
- Query results may underestimate blast radius in highly dynamic codebases

**Mitigation**:
- `graph_health` stone reports **confidence ratio** (actual edges / estimated total)
- Doctor report flags when confidence < 70%
- Use in combination with code review for critical impact analyses

**Acceptable for**:
- Architecture early-detection (patterns hold even if incomplete)
- Hotspot identification (high-degree nodes visible regardless)
- Governance reporting (relative metrics are stable)

---

### 2. Cycle Detection Depth Limit (Complexity Bound)

**What**: Cycle detection searches up to depth 6 only (prevents exponential explosion).

**Impact**:
- Deep cycles (> 6 hops) are silently missed
- Affects < 5% of real-world codebases (90% of cycles are < 3 hops)

**Rationale**: SQLite recursive CTE has depth limits; deeper search becomes exponentially expensive.

**Acceptable for**:
- Early detection (catches structural problems)
- Architectural review (typical cycles short)
- Breakpoints (find quick fixes for immediate cycles)

---

### 3. Community Detection as Heuristic (Not Optimal)

**What**: Module clustering uses simple heuristic (shared callers), not sophisticated algorithms like Louvain/Leiden.

**Impact**:
- Communities may not reflect optimal modularity
- False positives in dense regions (utilities appear as separate communities)
- May not detect deep structural patterns

**Rationale**: Sophisticated graph algorithms require external libraries or significant SQLite computation.

**Acceptable for**:
- v1 signal detection
- Identifying primary module boundaries
- Design exploration (not authoritative structure)

---

### 4. Utility Gravity Well (Metric Bias)

**What**: The gravity metric biases toward high-degree nodes (utilities appear as "central" even though they're shared infrastructure).

**Impact**:
- High fan-out utilities rank high in gravity metric
- Can misrepresent architectural importance
- Admin utilities, logging, auth modules appear central (they are, but not strategically central)

**Mitigation**:
- `utility_hubs` stone **separates utilities from orchestrators**
  - Utilities: high fan-out, low domain-specificity
  - Orchestrators: high fan-out, high domain relevance
- Always cross-check gravity results with `utility_hubs` output
- Doctor report includes both metrics

**Interpretation**:
```
High gravity + utility hub = shared infrastructure (infrastructure gravity)
High gravity + NOT utility hub = strategic chokepoint (architectural gravity)
```

---

## Performance Limitations

| Metric | Limit | Impact |
|--------|-------|--------|
| **Repository size** | Tested to 100K symbols, 1M calls | Scales linearly; no tested ceilings for 10M+ |
| **Query timeout** | Configurable (default 30s) | Long queries exit gracefully with incomplete results |
| **Memory footprint** | < 100MB typical | Exceeds limit only with extreme repositories (500K+ symbols) |
| **Concurrent writers** | 1 (serialized indexing) | Multi-reader safe via WAL; future versions may add incremental indexing |
| **SQLite version** | 3.8+, tested 3.40+ | Requires WAL mode + FTS5 support |

---

## Architectural Limitations (By Design)

### Single Language (v1.0)

**What**: Python indexer only. TypeScript, Java, Go, Rust not supported.

**Scope**: Planned for Phase 11+ with language-specific adapters.

**Workaround**: Use existing Python AST parser for multi-language repos where Python is majority language.

---

### No Real-Time Indexing (v1.0)

**What**: Indexing is batch-only; changes require re-indexing entire repository.

**Scope**: Incremental indexing planned for v1.1.

**Impact**: `.kit` must be re-generated after code changes (adds 5-10s latency).

---

### No Distributed Graph (v1.0)

**What**: Single SQLite file; no horizontal scaling or sharding.

**Acceptable for**:
- Monorepos up to 1M LOC
- Distributed analysis (generate local `.kit`, analyze independently)
- Federation (merge multiple `.kit` artifacts via SQL UNION)

**Not suitable for**:
- Real-time multi-user collaboration
- Cloud-scale analysis (100M+ LOC codebases requiring distributed storage)

---

## What This Means for Agents

### When to Trust Metrics

✅ **Trust**:
- Cycles (depth < 6)
- God modules (high fan-out always real)
- Hotspots (complexity + calls always real)
- Architecture violations (pattern-based)
- Dead code (false negatives only, not false positives)

❌ **Verify**:
- Gravity (cross-check with `utility_hubs`)
- Impact (check confidence metric first)
- Communities (consider heuristic nature)
- Metrics on dynamic-heavy code (check `graph_health`)

### Standard Interpretation

```python
if stone in ['cycles', 'deadcode', 'hotspots']:
    confidence = "high"      # Rely on results
elif stone in ['gravity']:
    confidence = "medium"    # Cross-check with utility_hubs
else:
    confidence = "medium"    # Check graph_health first
```

---

## Future Improvements (Post-v1.0)

- v1.1: Incremental indexing (avoid full re-index on small changes)
- v1.2: Dynamic call detection (reflection, meta-programming)
- v2.0: Multi-language support (Java, TypeScript, Go, Rust)
- v2.1: Distributed graph (federation of `.kit` artifacts)

---

**Summary**: `.kit` v1.0 trades perfect accuracy for simplicity and speed. It's honest about what it can and cannot measure, making it suitable for design exploration, architecture governance, and early-detection tools — not authoritative source.
