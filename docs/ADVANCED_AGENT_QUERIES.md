# Advanced Agent Queries (.kit)

This document defines the **query-time intelligence layer** of the `.kit` engine. All analysis capabilities are implemented as SQL queries executed directly on the local SQLite graph database.

## System Philosophy
The `.kit` platform is designed as an AI-native code observability layer:
- **SQLite over servers**: Sub-50ms local intelligence.
- **Query-time intelligence**: Logic resides in SQL, not the engine.
- **Token-efficient outputs**: Minimal JSON footprint.
- **Agent-first design**: Deterministic reasoning bridge.

---

## 💎 1. Impact Compression (Space Stone)
**Purpose**: Reduce large dependency graphs into a minimal set of impacted modules.

```sql
WITH impact AS (
    SELECT caller, file FROM calls WHERE callee = :target
),
module_rollup AS (
    SELECT substr(file, 1, instr(file, '/')-1) AS module, COUNT(*) AS cnt
    FROM impact GROUP BY module
)
SELECT json_group_object(COALESCE(NULLIF(module, ''), 'root'), cnt) AS modules FROM module_rollup;
```

---

## 💎 2. Importance Ranking (Power Stone)
**Purpose**: Detect architectural "hubs" using local degree centrality.

```sql
WITH deg AS (
    SELECT caller AS node, COUNT(*) AS d FROM calls GROUP BY caller
    UNION ALL
    SELECT callee AS node, COUNT(*) AS d FROM calls GROUP BY callee
),
centrality AS (
    SELECT node, SUM(d) AS score FROM deg GROUP BY node
)
SELECT node FROM centrality ORDER BY score DESC LIMIT 10;
```

---

## 💎 3. Risk Hotspot Detection (Time Stone)
**Purpose**: Predict bug-prone areas by combining structural importance with git churn.
**Heuristic**: `risk = centrality * churn`

---

## 💎 4. Architectural Layer Guard (Reality Stone)
**Purpose**: Detect forbidden cross-layer calls (e.g., `db -> api`).

```sql
WITH layers AS (
  SELECT caller_file, callee_file,
    CASE WHEN caller_file LIKE 'api/%' THEN 3 WHEN caller_file LIKE 'core/%' THEN 2 ELSE 1 END AS src_l,
    CASE WHEN callee_file LIKE 'api/%' THEN 3 WHEN callee_file LIKE 'core/%' THEN 2 ELSE 1 END AS dst_l
  FROM edges
)
SELECT caller_file, callee_file FROM layers WHERE src_l < dst_l;
```

---

## 💎 5. Cycle Detection (Mind Stone)
**Purpose**: Identify circular dependencies signaling architectural rot.

```sql
WITH RECURSIVE walk(start, node, path) AS (
  SELECT src, dst, src || '→' || dst FROM edges
  UNION ALL
  SELECT w.start, e.dst, w.path || '→' || e.dst
  FROM walk w JOIN edges e ON e.src = w.node
  WHERE instr(w.path, e.dst) = 0 OR e.dst = w.start
)
SELECT path || '→' || start AS cycle FROM walk WHERE node = start;
```

---

## 💎 6. God Module Detection (Soul Stone)
**Purpose**: Locate modules that absorb excessive coupling.
**Metric**: `fan_in + fan_out`

---

## 💎 7. Inferred Architecture (Vision Stone)
**Purpose**: Automatically map codebase layers without a manifest.
**Formula**: `layer_score = fan_out - fan_in` (Quantized via `NTILE(4)`)

---

## 🩺 8. Kit Doctor
**Purpose**: Run full codebase health diagnostics in sub-50ms.

```sql
SELECT json_object(
  'god_modules', (SELECT json_group_array(node) FROM god),
  'fan_in_bottlenecks', (SELECT json_group_array(node) FROM bottleneck),
  'layer_health', (SELECT layer_health FROM collapse)
) AS kit_doctor_report;
```

---

## Design Principles
- **No Hidden Intelligence**: Logic must remain transparent SQL.
- **Agent API**: Prefer raw JSON over human-readable formatting.
- **O(E) Efficiency**: All queries must remain sub-linear or close to it.
