# Hotfix v1.2.1: Configuration-only Workaround (kit-agent)

The 300s timeout in `kit-agent ask` is a known issue in v1.2.0 GA caused by sequential TCP discovery loops. Since the `kit_agent` core is under [ARCHITECTURE LOCK], use the following configuration workarounds to achieve sub-second response times.

## 1. Force Provider (Recommended)
Bypass the discovery loop by explicitly naming your alive LLM provider.
```bash
kit-agent ask "Your task" --provider gemini
```

## 2. Refuse Local Discovery
If you do not have Jan/Local LLM running, force the system to skip discovery by setting a "Refuse" port. This prevents the TCP stack from waiting for a timeout.
```bash
# Unix/macOS/Linux
export JAN_BASE_URL="http://127.0.0.1:1"

# Windows (PowerShell)
$env:JAN_BASE_URL="http://127.0.0.1:1"
```

## 3. Verify Health
Run the doctor to ensure your providers are correctly configured.
```bash
kit-agent status
```

---
*Note: These workarounds maintain [ARCHITECTURE LOCK] while resolving UX "clinical death" latency.*
