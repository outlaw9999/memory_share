# 🔍 v1.2.3 Execution Graph Reconstruction

> **Purpose**: Map ALL modules to execution flow
> **Status**: Real (not design)

---

## 📊 Module Inventory

| Module | File | Status | Hot Path? |
|--------|------|--------|-----------|
| SAMBrain | kit_cognitive_core.py | ✅ ACTIVE | learn/search/recall |
| auto_route | cli/auto_route.py | ✅ ACTIVE | learn --auto only |
| kit_reflect | core/kit_reflect.py | ✅ ACTIVE | reflect command |
| kit_decision | core/kit_decision.py | ✅ ACTIVE | reflect command |
| kit_governance | core/kit_governance.py | ✅ ACTIVE | preflight command |
| fast_guard | guard/fast_guard.py | ✅ ACTIVE | preflight command |
| kit_platform | core/kit_platform.py | ✅ ACTIVE | CLI utilities |
| file_system | core/file_system.py | ✅ ACTIVE | CLI utilities |
| schema_factory | core/schema_factory.py | ✅ ACTIVE | SAMBrain init |
| memory_router | core/memory_router.py | ⚠️ PARTIAL | attach_global only |
| storage_adapter | core/storage_adapter.py | ❌ UNUSED | not imported anywhere |
| kit_invariants | core/kit_invariants.py | ⚠️ LATENT | imported but not enforced |
| kit_vantage | core/kit_vantage.py | ⚠️ LATENT | only called in reflect --deep |
| risk_engine | analysis/risk_engine.py | ❌ LATENT | only in security_lens |
| security_lens | analysis/security_lens.py | ❌ LATENT | only in reflect --deep |
| shadow | core/shadow.py | ❌ LATENT | only in preflight |
| l3_registry | core/l3_registry.py | ❌ GHOST | never imported |
| runtime/ | runtime/*.py | ❌ GHOST | never imported |
| adaptive_trainer | cli/adaptive_trainer.py | ❌ GHOST | never imported |
| doctor | cli/doctor.py | ⚠️ SIDE | doctor command |

---

## 🔥 Active Execution Paths

### Path 1: `kit learn` (without --auto)

```
CLI
 ↓
main.py: args.command == "learn"
 ↓
api.get_brain().learn()
   ↓
SAMBrain.learn()
   ├─ sanitize_global_metadata()
   ├─ enforce_no_global_contamination()
   ���─ write SQLite
   └─ RETURN fact_id
```

**Authority**: SAMBrain.learn()

---

### Path 2: `kit learn --auto`

```
CLI
 ↓
main.py: args.command == "learn" + args.auto
 ↓
auto_route.route_content(content)
   ├─ detect_secret() → BLOCK/DROP
   ├─ detect_noise() → DROP
   └─ idempotency_check() → SKIP
 ↓
api.get_brain().learn()
   ↓
SAMBrain.learn()
   └─ write SQLite
```

**Authority**: SAMBrain.learn() (auto_route is filter only)

---

### Path 3: `kit recall`

```
CLI
 ↓
main.py: args.command == "recall"
 ↓
api.recall()
   ↓
SAMBrain.recall()
   ├─ Phase 1: Local brain
   ├─ Phase 2: Global brain (optional)
   └─ calculate_runtime_score()
```

**Authority**: SAMBrain.recall()

---

### Path 4: `kit search`

```
CLI
 ↓
main.py: args.command == "search"
 ↓
api.search()
   ↓
SAMBrain.search()
   ├─ FTS local
   └─ FTS global
```

---

### Path 5: `kit reflect`

```
CLI
 ↓
main.py: args.command == "reflect"
 ↓
api.reflect_check()
   ↓
kit_reflect.run_reflect()
   ├─ extract_signals()
   ├─ apply_security_lens()  ← calls risk_engine!
   └─ check_gap_detector()
 ↓
kit_decision.decide()
   └─ BLOCK/WARN/PASS
```

**Decision Authority**: kit_decision.decide()

---

### Path 6: `kit preflight`

```
CLI
 ↓
main.py: args.command == "preflight"
 ↓
api.preflight_check()
   ↓
kit_governance.run_preflight()
   ├─ execute_l1_guard()  ← fast_guard
   ├─ run_shadow_scan()   ← shadow
   ├─ Semantic check
   ├─ Version check
   └─ Noise check
```

**Decision Authority**: kit_governance.run_preflight() (own scoring)

---

### Path 7: `kit reflect --deep`

```
CLI
 ↓
main.py: args.command == "reflect" + args.deep
 ↓
api.reflect_check(deep=True)
   ↓
kit_reflect.run_reflect(deep=True)
   ├─ extract_signals()
   ├─ invoke_vantage()   ← VANTAGE ACTIVATED!
   ├─ apply_security_lens()
   └─ check_gap_detector()
 ↓
kit_decision.decide()
```

**Vantage Status**: Only activated with --deep flag

---

## ⚠️ Disconnected Modules (Not in Hot Path)

### 1. runtime/ folder
- **Status**: ❌ GHOST
- **Import**: Never imported in kit/ or cli/
- **Reason**: Experimental, not connected to SAMBrain

### 2. l3_registry
- **Status**: ❌ GHOST  
- **Import**: Never imported anywhere
- **Reason**: Documentation only, no enforcement

### 3. adaptive_trainer
- **Status**: ❌ GHOST
- **Import**: Never imported
- **Reason**: Unfinished

### 4. storage_adapter
- **Status**: ❌ UNUSED
- **Import**: memory_router imports but doesn't use
- **Reason**: Legacy, not connected

---

## ⚠️ Latent Capabilities (Can be activated)

### 1. Vantage (kit_vantage.py)
- **Current**: Only called in `reflect --deep`
- **Can activate in**:
  - `learn --auto` (before write)
  - `preflight` (before commit)
- **Missing connection**: Not in any critical path

### 2. risk_engine
- **Current**: Only via security_lens in reflect
- **Can activate in**:
  - kit_governance
  - auto_route
- **Missing connection**: Not integrated

### 3. kit_invariants
- **Current**: Imported in SAMBrain but enforcement is partial
- **Can activate**:
  - Full enforcement in learn()
  - preflight checks
- **Missing connection**: Partial import, not enforced everywhere

### 4. shadow
- **Current**: Only in kit_governance
- **Can activate in**:
  - learn flow
  - reflect flow
- **Missing connection**: Not in main path

---

## 🎯 Vantage Integration Points

### Current Flow

```
kit reflect --deep
    ↓
invoke_vantage() → signals
    ↓
security_lens.apply() → more signals
    ↓
kit_decision.decide()
```

### Should Be (v1.2.4)

```
kit learn --auto
    ↓
auto_route (firewall)
    ↓
invoke_vantage() → structural check  ← MISSING!
    ↓
SAMBrain.learn()
```

### Alternative: preflight

```
kit preflight
    ↓
fast_guard
    ↓
invoke_vantage()  ← SHOULD BE HERE
    ↓
kit_governance
```

---

## 📈 Full Graph (ASCII)

```
                           CLI (main.py)
                               │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   learn w/              recall/search           reflect
   --auto                                       │
        │                     │                     │
        ▼                     │                     ▼
   auto_route              SAMBrain            kit_reflect
   (firewall)                 │                     │
        │                    ▼                    ▼
        ▼               SQLite            security_lens
                            │                (risk_engine)
                            │                     │
                            │                    ▼
                            │               kit_decision
                            │                     │
                            ▼                     ▼
                       (truth)              BLOCK/WARN
```

---

## 🔴 Critical Missing Links

| Link | Should Connect | Current Status |
|------|----------------|----------------|
| Vantage → learn | auto_route after filtering | Not connected |
| Vantage → preflight | before governance | Not connected |
| risk_engine → learn | before write | Not connected |
| risk_engine → preflight | in L2 | Only in reflect |
| L3 → runtime | enforcement | Never called |
| shadow → learn | hygiene check | Only in preflight |
| runtime/ → kit/ | execution | Not connected |

---

## 🎯 Recommendations for v1.2.4

### Option A: Minimal (Connect Vantage only)

```
kit learn --auto
    ↓
auto_route
    ↓
invoke_vantage()  ← ADD HERE
    ↓
SAMBrain.learn()
```

### Option B: Full Orchestration

```
kit learn --auto
    ↓
auto_route (firewall)
    ↓
invoke_vantage (structural)
    ↓
risk_engine (semantic)
    ↓
shadow (logging)
    ↓
SAMBrain.learn()
```

### Option C: RuntimeSpine (NOT recommended yet)

- Wait until Option A or B is proven
- Don't build new layer before mapping existing

---

## 🔍 Next Steps

1. **Verify Vantage works**: Test `kit reflect --deep` on a real file
2. **Map missing links**: Add Vantage to learn or preflight
3. **Test risk_engine integration**: Try in auto_route
4. **Cleanup ghost modules**: Mark l3_registry, runtime as experimental

---

*Generated from Execution Graph Audit v1.2.3*