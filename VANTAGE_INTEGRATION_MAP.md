# 🔥 Vantage Integration Map (Exact Hook Points)

> **Scope**: v1.2.3 → v1.2.4 Observer Injection
> **Status**: Line-level integration points identified

---

## 🎯 HOOK 1: `kit learn` (Primary Path)

### Location: `kit/cli/main.py`

```
Lines 577-611:
    577:     if getattr(args, "auto", False):
    578:         from kit.cli import auto_route
    579: 
    580:         res = auto_route.route_content(content)
    581:         status = res["status"]
    582: 
    583:         if status == "BLOCK":
    584:             print_diagnostic(...)
    585:             continue
    586:         if status == "DROP":
    587:             print_diagnostic(...)
    588:             continue
    589:         if status == "SKIP":
    590:             print_diagnostic(...)
    591:             continue
    592: 
    593:         struct_hash = res["hash"]
    594:         to_global = res["route"] == "GLOBAL"
    595: 
    596:     fact_id = api.get_brain().learn(    ← CURRENT: SAMBrain write
```

### Insert AFTER line 594 (BEFORE SAMBrain.learn):

```python
# --- VANTAGE OBSERVER (v1.2.4) ---
if getattr(args, "auto", False) and getattr(args, "vantage", False):
    try:
        from kit.core.kit_vantage import invoke_vantage
        
        # Get structural signals from Vantage
        # Note: requires file_path or analyze content
        v_signals = invoke_vantage(Path(args.file or "main.py"))
        
        if v_signals:
            # Attach as metadata, NOT blocking
            for sig in v_signals:
                print_diagnostic(f"[VANTAGE] Signal: {sig.uid} | {sig.confidence}")
            
            # Optional: attach to metadata
            metadata["vantage_signals"] = [
                {"uid": s.uid, "confidence": s.confidence} 
                for s in v_signals
            ]
    except Exception as e:
        # Graceful fallback: Vantage is observer, not blocker
        print_diagnostic(f"[VANTAGE] Skipped: {e}")
```

### Add CLI flag in learn parser:

```python
# Around line 316 in learn_p definition
learn_p.add_argument("--vantage", action="store_true", 
                 help="Invoke Vantage structural sensor (observer mode)")
```

---

## 🎯 HOOK 2: `kit preflight`

### Location: `kit/core/kit_governance.py`

```
Lines 68-90 (approx):
    68:     # --- LAYER 1: Fast Guard (Sacrificial Layer) ---
    69:     guard_res = execute_l1_guard(diff_output, staged_files)
    70: 
    71:     # Carry over any issues/warnings from L1 (Massive commit, etc.)
    72:     result.issues.extend(guard_res.issues)
    73: 
    74:     if not guard_res.passed:
    75:         if guard_res.is_hard_block:
    76:             # Hard violation -> BLOCK immediately
    77:             result.status = "block"
    78:             result.score = 0.0
    79:             return result
    80:         else:
    81:             # Soft failure (Artifact Only). No actual code for L3 to analyze.
    82:             result.status = "pass"
    83:             return result
    84: 
    85:     # If L1 passes (Valid text, possibly truncated) -> Proceed to L3
    86:     clean_diff = guard_res.clean_diff
    87:     loc_changed = guard_res.loc_changed
    88:     staged_files = guard_res.staged_files
    89: 
    90:     # --- LAYER 2: Structural Analysis (Placeholder for L2 Sensors like Vantage) ---
    91:     # Shadow Signal Collection (Phase 0: Regex Sensors)
    92:     from kit.core.shadow import run_shadow_scan
```

### Insert AFTER line 88 (AFTER L1, BEFORE L2 shadow):

```python
# --- VANTAGE STRUCTURAL CHECK (v1.2.4) ---
# Run Vantage after L1 fast guard passes
# This is observer mode: adds signals but doesn't block
if getattr(args, "deep", False):  # or check for vantage flag
    try:
        from kit.core.kit_vantage import invoke_vantage
        
        for f in staged_files:
            if f != "<stdin>" and Path(f).suffix in (".py", ".rs", ".js", ".ts"):
                v_signals = invoke_vantage(Path(f))
                if v_signals:
                    # Add to signals list, NOT blocking
                    for sig in v_signals:
                        result.issues.append({
                            "type": "structural",
                            "message": f"[VANTAGE] {sig.uid}: {sig.evidence}"
                        })
    except Exception as e:
        # Graceful fallback
        pass
```

### Add parameter to run_preflight:

```python
def run_preflight(
    commit_msg: str,
    brain: SAMBrain,
    strict_mode: bool = False,
    limit: int = 20,
    diff_text: str | None = None,
    deep_scan: bool = False,  # NEW: Vantage flag
) -> PreflightResult:
```

---

## 🎯 HOOK 3: `kit reflect --deep` (Already Connected)

### Location: `kit/core/kit_reflect.py`

```
Line 219:
    219:         from kit.core.kit_vantage import invoke_vantage
    220: 
    221:         semantic_signals = apply_security_lens(file_path, v_deep_signals)
```

### Already working - no changes needed

---

## 📊 Integration Summary

| Hook | Location | Status | Behavior |
|------|----------|--------|---------|
| learn --auto | main.py:596 | NEW | Observer + metadata |
| preflight | governance.py:88 | NEW | Observer + signals |
| reflect --deep | reflect.py:219 | ✅ EXISTING | Already connected |

---

## 🔒 Key Invariants to Maintain

### Vantage MUST:

1. ✅ Never block write operation
2. ✅ Never decide commit status
3. ✅ Always fail gracefully (observer mode)
4. ✅ Attach metadata when successful

### Vantage MUST NOT:

1. ❌ Replace kit_decision
2. ❌ Duplicate L3 Registry
3. ❌ Add orchestration layer

---

## 🔧 Minimal Diff (Patch Format)

### Patch 1: learn hook

```diff
--- a/kit/cli/main.py
+++ b/kit/cli/main.py
@@ -316,6 +316,7 @@ learn_p.add_argument("--auto", action="store_true", help="Use v1.2.3 intelligent routing (recommended)")
+learn_p.add_argument("--vantage", action="store_true", help="Invoke Vantage structural sensor (observer mode)")
 
 # In learn command, after auto_route:
+if getattr(args, "vantage", False):
+    from kit.core.kit_vantage import invoke_vantage
+    v_signals = invoke_vantage(Path(args.file or "main.py"))
+    if v_signals:
+        metadata["vantage_signals"] = [{"uid": s.uid, "confidence": s.confidence} for s in v_signals]
```

### Patch 2: preflight hook

```diff
# In kit_governance.py run_preflight():
+if deep_scan:
+    from kit.core.kit_vantage import invoke_vantage
+    for f in staged_files:
+        v_signals = invoke_vantage(Path(f))
+        for sig in v_signals:
+            result.issues.append({"type": "structural", "message": f"[VANTAGE] {sig.uid}"})
```

---

## 🧪 Testing Plan

### Test 1: learn --vantage

```bash
kit learn --auto --vantage --content "Test memory"
```

Expected: Output shows `[VANTAGE] Signal: STRUCTURAL:...` but write succeeds

### Test 2: preflight with deep

```bash
kit preflight -m "feat: add feature" --deep
```

Expected: Vantage signals added to issues but not blocking

### Test 3: reflect --deep

```bash
kit reflect --deep
```

Expected: Same as before (already working)

---

## 📦 Metadata Schema

When Vantage connects, memory stores:

```json
{
  "id": 123,
  "content": "...",
  "tag": "decision",
  "structural_hash": "abc123",
  "metadata": {
    "source": "cli",
    "vantage_signals": [
      {
        "uid": "STRUCTURAL:MUTATION",
        "confidence": "high",
        "evidence": "..."
      }
    ]
  }
}
```

---

## 🚀 Next Steps

1. **Test current reflect --deep**: Verify Vantage binary works
2. **Add --vantage flag to learn**: Minimal patch
3. **Monitor false positive rate**: Track accuracy
4. **Add to preflight (optional)**: If learn integration stable

---

*Generated: Exact Vantage Integration Map*
*Status: Ready for patch implementation*