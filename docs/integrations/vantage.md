# Vantage Integration (v1.0 - 2026-03-24)

## Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────┐
│   Agent     │────▶│  .kit Memory Kernel  │◀────│   .kit       │
│   (CLI)     │     │  (SQLite + FTS)     │     │  recall/     │
└──────────────┘     └──────────┬──────────┘     │  learn       │
                              │                └──────────────┘
                              │ adapter call
                              ▼
                     ┌─────────────────────┐
                     │ vantage_adapter.py   │
                     │  - parse UTF-8 text  │
                     │  - filter top-k     │
                     │  - sanitize ≤30w    │
                     └──────────┬──────────┘
                              │ subprocess
                              ▼
                     ┌─────────────────────┐     ┌──────────────┐
                     │ kit-vantage.bat     │────▶│ Vantage CLI │
                     │  (Windows shim)     │     │ (Rust 2024) │
                     └─────────────────────┘     └──────────────┘
```

## Usage

### 1. Call Vantage + Parse (Python)
```python
from tools.vantage_adapter import call_vantage, filter_signals

result = call_vantage('path/to/file.rs')
signals = filter_signals(result)
for s in signals:
    print(f"[{s['type']}] {s['content']}")
```

### 2. Inject signals to .kit
```python
from tools.vantage_adapter import call_vantage, filter_signals, inject_to_kit

result = call_vantage('path/to/file.rs')
signals = filter_signals(result)
inject_to_kit(signals)  # atomic learn ≤30 words/signal
```

### 3. CLI Pipeline (Windows)
```cmd
kit-vantage.bat verify file.rs | python tools\vantage_adapter.py --json
```

## Signal Types
| Type | Priority | Description |
|------|----------|-------------|
| error | 10 | Vantage runtime errors |
| observation | 3 | @epistemic tag status |
| target | 1 | File being verified |
| mode | 1 | Language mode detected |

## Limitations
- Vantage only supports .rs files (AST parsing)
- Markdown mode not ready
- No semantic analysis (by design)
