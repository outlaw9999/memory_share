# Vantage Integration (v1.0 - 2026-03-24)

## Overview

Vantage is the structural sensor used by `.kit` when we need code-shape awareness beyond raw text. It is not a generic file hasher. It works best for supported source languages where structural signals can be extracted reliably.

## Integration Architecture

```text
Agent / CLI
  -> .kit memory kernel
  -> Vantage adapter
  -> kit-vantage shim
  -> Vantage CLI
```

### Responsibilities

- **.kit** stores and recalls memory
- **Vantage adapter** parses and filters structural signals
- **kit-vantage shim** bridges the repository workflow to the external Vantage binary
- **Vantage CLI** produces structural verification signals

## Usage

### 1. Call Vantage and Parse Signals

```python
from tools.vantage_adapter import call_vantage, filter_signals

result = call_vantage("path/to/file.rs")
signals = filter_signals(result)
for signal in signals:
    print(f"[{signal['type']}] {signal['content']}")
```

### 2. Inject Signals into `.kit`

```python
from tools.vantage_adapter import call_vantage, filter_signals, inject_to_kit

result = call_vantage("path/to/file.rs")
signals = filter_signals(result)
inject_to_kit(signals)
```

### 3. Windows CLI Pipeline

```cmd
kit-vantage.bat verify file.rs | python tools\vantage_adapter.py --json
```

## Signal Types

| Type | Priority | Description |
|------|----------|-------------|
| `error` | 10 | Vantage runtime errors |
| `observation` | 3 | `@epistemic` tag status |
| `target` | 1 | File being verified |
| `mode` | 1 | Language mode detected |

## Current Limitations

- Vantage is designed for structural code analysis, not generic baseline hashing
- Unanchored files may parse successfully but still return `no_anchor_found`
- Shell scripts such as `.bat` and `.ps1` are outside the supported structural scope
- Markdown support is not part of the current verification path
- Semantic analysis is intentionally out of scope
