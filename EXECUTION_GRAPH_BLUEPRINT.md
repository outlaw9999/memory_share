# 🧠 Execution Graph Blueprint v1.2.3

> **Purpose**: Full system mapping for v1.2.4 decision
> **Status**: Complete audit from codebase + execution traces

---

## 📊 Module Classification

### 🟢 ACTIVE (Hot Path - Execution Critical)

| Module | File | CLI Command | Role |
|--------|------|-----------|------|
| main.py | cli/main.py | ALL | CLI Orchestrator |
| api.py | api.py | ALL | Public API Boundary |
| SAMBrain | core/kit_cognitive_core.py | learn/search/recall | Core Executor |
| auto_route | cli/auto_route.py | learn --auto | Firewall Filter |
| kit_decision | core/kit_decision.py | reflect | Decision Engine |
| kit_governance | core/kit_governance.py | preflight | Commit Governance |
| fast_guard | guard/fast_guard.py | preflight | L1 Fast Filter |
| kit_reflect | core/kit_reflect.py | reflect | Signal Extractor |
| file_system | core/file_system.py | scan/reflect | File Utilities |
| kit_platform | core/kit_platform.py | ALL | Platform Utils |

### 🟡 LATENT (Exists, Not in Hot Path)

| Module | File | Should Connect To | Current Status |
|--------|------|------------------|----------------|
| kit_vantage | core/kit_vantage.py | learn --auto, preflight | Only reflect --deep |
| risk_engine | analysis/risk_engine.py | learn, preflight | Only via security_lens |
| security_lens | analysis/security_lens.py | reflect --deep | Partial |
| shadow | core/shadow.py | learn, preflight | Only preflight |
| kit_invariants | core/kit_invariants.py | learn | Partial import |
| memory_router | core/memory_router.py | SAMBrain | attach only |
| kit_reflect (gap) | core/kit_reflect.py | reflect | Partial execution |
| file_system (encoding) | core/file_system.py | ALL | Limited |

### 🔴 ORPHAN / UNUSED (Not Connected)

| Module | File | Reason |
|--------|------|--------|
| l3_registry | core/l3_registry.py | Documentation only, never imported |
| runtime/* | runtime/*.py | Experimental, not imported |
| storage_adapter | core/storage_adapter.py | Imported but unused |
| adaptive_trainer | cli/adaptive_trainer.py | Unfinished |
| doctor | cli/doctor.py | Side command only |

---

## 🔥 Hot Path Execution Flows

### CLI Entry → Response Mapping

```
CLI command          → main.py section     → api call          → SAMBrain     → Output
─────────────────────────────────────────────────────────────────────────────
kit learn           → "learn"          → api.learn()      → learn()     → fact_id
kit learn --auto    → "learn"+auto    → auto_route      → learn()     → fact_id
kit recall         → "recall"        → api.recall()     → recall()    → list[Memory]
kit search         → "search"        → api.search()    → search()    → list[Memory]
kit reflect        → "reflect"      → api.reflect()   → reflect()   → signals
kit reflect --deep  → "reflect+deep" → api.reflect()   → reflect()   → signals+vantage
kit preflight      → "preflight"    → api.preflight() → governance  → score+issues
kit scan          → "scan"         → file_system    → safe_walk() → file list
kit stats         → "stats"       → api.stats()    → get_stats() → counts
kit doctor        → "doctor"      → doctor.run()  → diagnostics → report
```

---

## 🎯 Decision Authority Mapping

### Who Controls Output?

| Operation | First Authority | Final Authority | Override? |
|-----------|---------------|---------------|-----------|
| learn | auto_route | SAMBrain.learn() | No (blocked) |
| learn --auto | auto_route + user | SAMBrain.learn() | --force flag |
| recall | SAMBrain | SAMBrain.recall() | No |
| reflect | kit_reflect | kit_decision.decide() | --mode=advisory |
| reflect --deep | Vantage | kit_decision.decide() | --mode=advisory |
| preflight | fast_guard | kit_governance | --mode=silent |
| scan | file_system | safe_walk() | No |

### Conflict Resolution Priority

```
 BLOCK path:
  1. auto_route: BLOCK → STOP
  2. kit_decision: BLOCK → STOP
  3. kit_governance: BLOCK → STOP

 WARN path:
  1. kit_decision: WARN → Continue
  2. kit_governance: WARN → Continue

 PASS path:
  1. All other → Continue
```

---

## 🔌 Vantage Injection Points

### Currently: reflect --deep ONLY

```
kit reflect --deep
  → api.reflect_check(deep=True)
  → kit_reflect.run_reflect(deep=True)
  → invoke_vantage() ← ONLY HERE
  → apply_security_lens()
  → kit_decision.decide()
```

### Recommended Injection Points

#### Point A: learn --auto (Before write)

```
kit learn --auto
  → auto_route (filter)
  → invoke_vantage(file_path)  ← NEW: structural check
  → IF high_confidence_signals:
      → WARN or BLOCK
  → ELSE:
      → SAMBrain.learn()
```

#### Point B: preflight (After L1, before L2)

```
kit preflight
  → fast_guard (L1)
  → invoke_vantage()  ← NEW: structural validation
  → shadow (L2)
  → governance (L3)
```

#### Point C: Both (Recommended)

```python
# Minimal patch: Add to kit learn --auto only
# Full patch: Add to preflight
```

---

## 📈 Influence Weights

### Module → Decision

| Module | Influence Score (0-1) | Type |
|--------|---------------------|------|
| SAMBrain.learn() | 1.0 | Write Authority |
| auto_route | 0.8 | Pre-filter |
| kit_decision | 0.9 | Decision |
| kit_governance | 0.7 | Governance |
| kit_reflect | 0.6 | Analysis |
| Vantage | 0.9 | Structural Truth |
| risk_engine | 0.5 | Advisory |
| security_lens | 0.5 | Advisory |
| fast_guard | 0.6 | L1 Filter |
| shadow | 0.4 | Logging |

### Edge Weights (For Graph Analysis)

| From | To | Weight | Type |
|------|-----|--------|-------|
| main.py | api.py | 1.0 | Direct |
| api.py | SAMBrain | 1.0 | Direct |
| api.py | kit_reflect | 0.3 | Conditional |
| api.py | kit_governance | 0.2 | Command |
| auto_route | SAMBrain | 0.6 |learn --auto only |
| kit_reflect | kit_decision | 0.5 | reflect only |
| invoke_vantage | kit_reflect | 0.2 | --deep only |

---

## 🗺️ Execution Graph (ASCII)

```
                    ┌──────────────────────────────────────┐
                    │        CLI (main.py)                  │
                    │   All commands enter here             │
                    └──────────────┬───────────────────┘
                                 │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
   learn/recall/search    reflect          preflight
          │                        │                        │
          ▼                        ▼                        ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │ auto_route  │         │ kit_reflect │         │ fast_guard │
   │ (--auto)   │         │            │         │            │
   └─────┬──────┘         └─────┬──────┘         └─────┬──────┘
        │                       │                       │
        │              ┌────────┴────────┐          │
        ▼              ▼                ▼          ▼
   ┌─────────┐   invoke_         shadow       governance
   │ SAMBrain│    vantage    (--deep)       (L3)
   │ .learn │   (LATENT)                    │
   └────┬────┘                              │
        │                                ▼
        │                         kit_governance
   ┌────┴────┐                      ┌──────┴─────┐
   │         │                      │            │
   ▼         ▼                      ▼            ▼
  SQLite  kit_reflect   apply_security_lens   score+issues
  (truth)  (signals)    (risk_engine)
           │                 │
           ▼                 ▼
       kit_decision      BLOCK/WARN/PASS
         │
         ▼
       BLOCK/WARN
```

---

## 🎯 v1.2.4 Minimal Patch Set

### Not Recommended (Yet)

- RuntimeSpine (premature abstraction)
- L3 enforcement (no runtime connection)
- New decision engine (current works)

### Recommended (Patch)

#### Patch 1: Activate Vantage in learn --auto

```python
# cli/main.py, in learn command after auto_route
if args.auto and getattr(args, "vantage", False):
    # Call Vantage if --vantage flag provided
    from kit.core.kit_vantage import invoke_vantage
    signals = invoke_vantage(Path(file_path))
    if signals:
        for s in signals:
            print(f"[VANTAGE] {s.uid}: {s.confidence}")
```

#### Patch 2: Connect risk_engine to auto_route

```python
# cli/auto_route.py, add risk scoring
# After secret/noise detection
if content:
    from kit.analysis.risk_engine import RiskEngine
    risk = RiskEngine()
    score = risk.assess(content)
    if score > 0.8:
        # flag as sensitive
        pass
```

#### Patch 3: Add Vantage to preflight (optional)

```python
# kit_governance.py, after L1 fast_guard
if deep_scan:
    from kit.core.kit_vantage import invoke_vantage
    v_signals = invoke_vantage(file_path)
    # add to result
```

---

## 🔴 Dead Code Candidates

| Module | Line Count | Recommendation |
|--------|----------|--------------|
| l3_registry.py | ~300 | Document only, can remove from hot |
| runtime/* | ~500 | Move to kit_extension/ or archive |
| adaptive_trainer.py | ~100 | Complete or remove |
| storage_adapter.py | ~50 | Remove import |

---

## 📊 Statistics

- Total Python files: 28
- Active modules: 10 (36%)
- Latent modules: 8 (29%)
- Orphan/unused: 10 (36%)
- CLI commands: 18
- Execution paths: 7
- Decision authorities: 3

---

## 🎯 Next Steps

1. **Test Vantage**: Run `kit reflect --deep` on real code
2. **Add flag**: `kit learn --vantage` (opt-in structural check)
3. **Monitor**: Track false positive rate
4. **Gradual**: Add to preflight if stable
5. **Re-evaluate**: Need for Spine after integration

---

*Generated: v1.2.3 Execution Graph Blueprint*
*Status: Ready for v1.2.4 decision*