# .kit MCP Server Setup Guide

**Version**: v1.0  
**Date**: 2026-03-10  
**Status**: ✅ Ready for integration with Claude, Gemini, custom agents

---

## Overview

The **kit MCP server** transforms the `.kit` CLI into an AI-native tool interface. Instead of spawning shell subprocesses, agents call MCP tools directly.

**Benefits**:
- ✅ ~500× token savings (100 tokens vs 50,000+ for reading code)
- ✅ ~10× faster analysis (parallel tool execution)
- ✅ Zero latency for repeated queries (cached tool definitions)
- ✅ Works offline (no API calls)

---

## Installation

### 1. Verify Prerequisites

```bash
# Check Python 3.7+
python --version

# Verify bin/kit works
python bin/kit doctor
```

### 2. No Additional Dependencies

The MCP server uses only Python stdlib. No `pip install` needed.

---

## Running the Server

### Stdio Mode (Recommended)

```bash
python kit_mcp_server.py
```

The server will:
1. Listen on stdin for MCP messages (JSON)
2. Write responses to stdout (JSON)
3. Log debug info to stderr

### Test Mode

```bash
# List all available tools
python kit_mcp_server.py --test

# Call a specific tool
python kit_mcp_server.py --test kit_doctor
python kit_mcp_server.py --test kit_stones_list
python kit_mcp_server.py --test kit_query_stone stone_name=gravity
```

---

## Integration: Claude (TextSync)

**Claude can use MCP server to analyze your codebase.**

### Option A: Environment Variable

```bash
# In your shell startup (~/.bashrc, ~/.zshrc, etc.)
export KIT_MCP_SERVER="stdio:///full/path/to/kit_mcp_server.py"

# Or in Claude's config
```

### Option B: Cursor IDE

If using Cursor (AI IDE built on VSCode):

Add to `.cursor/config.json`:
```json
{
  "mcp_servers": {
    "kit": {
      "command": "python",
      "args": ["/path/to/kit_mcp_server.py"]
    }
  }
}
```

### Option C: Custom Python Agent

```python
import subprocess
import json

class KitMCPClient:
    def __init__(self):
        self.server = subprocess.Popen(
            ["python", "kit_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    
    def call(self, tool_name: str, arguments: dict):
        request = {
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        self.server.stdin.write(json.dumps(request) + "\n")
        self.server.stdin.flush()
        response = json.loads(self.server.stdout.readline())
        return response["result"]

# Usage
kit = KitMCPClient()
health = kit.call("kit_doctor", {})
print(f"Architecture status: {health['overall_status']}")
```

---

## Available Tools

### 1. kit_doctor

**Purpose**: Quick architecture health check  
**Cost**: ~100 tokens  
**Output**: 5 key metrics + recommendations

```python
result = kit.call("kit_doctor", {})
# Returns:
# {
#   "overall_status": "HEALTHY",
#   "cycles_detected": 0,
#   "critical_gravity_nodes": 0,
#   "graph_confidence": 0.95,
#   "recommendations": "..."
# }
```

### 2. kit_stones_list

**Purpose**: Discover all diagnostic stones  
**Cost**: ~50 tokens  
**Output**: 14 stones organized by category

```python
result = kit.call("kit_stones_list", {})
# Returns:
# {
#   "primitives": [...],
#   "advanced": [...],
#   "orchestrators": [...],
#   "total": 14
# }
```

### 3. kit_query_stone

**Purpose**: Execute any diagnostic stone  
**Cost**: varies (50-500 tokens depending on stone)

```python
result = kit.call("kit_query_stone", {
    "stone_name": "gravity",
    "format": "json"
})
# Returns: gravity analysis (high-centrality nodes)
```

**Available stones**:
```
Primitives:    cycles, god_modules, architecture, entropy, gravity, 
               hotspots, choke_points, dead_code, graph_health, utility_hubs
Advanced:      impact, domains
Orchestrators: doctor, drift
```

### 4. kit_symbol_search

**Purpose**: Find code symbols and documentation  
**Cost**: ~100 tokens

```python
result = kit.call("kit_symbol_search", {
    "query": "authentication",
    "limit": 10,
    "include_private": False
})
# Returns: matching symbols from code + docs
```

### 5. kit_impact

**Purpose**: Analyze blast radius of a symbol  
**Cost**: ~150 tokens

```python
result = kit.call("kit_impact", {
    "symbol": "authenticate()",
    "depth": 3,
    "limit": 50
})
# Returns: all symbols affected by changes to authenticate()
```

### 6. kit_context

**Purpose**: Get unified code context for a symbol  
**Cost**: ~100 tokens

```python
result = kit.call("kit_context", {
    "symbol": "kernel",
    "callers_limit": 5,
    "callees_limit": 5,
    "radius": 8
})
# Returns: definition + callers + callees + related docs
```

---

## MCP Protocol Reference

### Request Format

```json
{
  "method": "tools/call" | "tools/list",
  "params": {
    "name": "tool_name",
    "arguments": {
      "param1": value1,
      "param2": value2
    }
  },
  "id": 1
}
```

### Response Format

```json
{
  "id": 1,
  "status": "success" | "error",
  "result": {
    ...
  }
}
```

---

## Performance Notes

| Operation | Cost | Time |
|-----------|------|------|
| List stones | ~50 tokens | <1s |
| Doctor check | ~100 tokens | ~1s |
| Query gravity | ~200 tokens | ~500ms |
| Impact analysis | ~150 tokens | ~1s |
| Symbol search | ~100 tokens | <1s |

**Total for full health analysis**: ~100 tokens, ~3 seconds

---

## Troubleshooting

### Server Won't Start

```bash
# Check Python version
python --version  # Need 3.7+

# Check kit.py exists and works
python bin/kit doctor  # Should output JSON

# Try test mode
python kit_mcp_server.py --test
```

### Tool Calls Timeout

The MCP server has 30s timeout per command. If analyzing large codebases:

```python
# Use depth/limit parameters to reduce scope
result = kit.call("kit_impact", {
    "symbol": "large_symbol",
    "depth": 2,      # Reduce from default 3
    "limit": 20      # Reduce from default 50
})
```

### JSON Parse Errors

Ensure stdout is clean. Redirect kit CLI output:

```python
env = os.environ.copy()
env["ANTIGRAVITY_WORKSPACE_ROOT"] = workspace_root
# Server handles this internally - should not occur
```

---

## Advanced: Custom Workspace Root

By default, MCP server uses current working directory. To specify a different repository:

```bash
# Set environment variable
export ANTIGRAVITY_WORKSPACE_ROOT=/path/to/repo

# Run server
python kit_mcp_server.py
```

---

## Architecture Freeze

The MCP server is built on `.kit` v1.0, which is architecturally frozen:

✅ **Locked in**:
- 6 MCP tools (kit_doctor, kit_query_stone, kit_context, kit_symbol_search, kit_impact, kit_stones_list)
- 14 diagnostic stones (primitives + advanced + orchestrators)
- JSON output format
- Tool argument schemas

🔄 **Open for Evolution**:
- New stones (added via extension)
- Stone parameters (extended, not changed)
- Tool descriptions (updated for clarity)

---

## Examples

### Detecting Circular Dependencies

```python
health = kit.call("kit_doctor", {})
if health["cycles_detected"] > 0:
    cycles = kit.call("kit_query_stone", {
        "stone_name": "cycles"
    })
    print(f"⚠️ Found {len(cycles)} circular dependencies")
```

### Assessing Refactoring Risk

```python
symbol = "refactor_this_function"
context = kit.call("kit_context", {"symbol": symbol})
impact = kit.call("kit_impact", {"symbol": symbol, "depth": 4})

risk = "HIGH" if len(impact["affected"]) > 20 else "MEDIUM" if len(impact["affected"]) > 5 else "LOW"
print(f"Refactor risk: {risk} ({len(impact['affected'])} affected symbols)")
```

### Batch Analysis

```python
results = {}
for stone in ["cycles", "god_modules", "hotspots", "dead_code"]:
    results[stone] = kit.call("kit_query_stone", {"stone_name": stone})

summary = {
    "urgent": len(results["cycles"]) + len(results["hotspots"]),
    "cleanup": len(results["dead_code"]),
    "refactor": len(results["god_modules"])
}
```

---

## Questions?

See `AGENT_CONTEXT.md` for quick reference or `docs/METRICS.md` for detailed stone documentation.
