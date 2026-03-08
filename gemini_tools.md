# Gemini Tool Integration

`memory_share.kit` exposes a minimal CLI interface that can be used as external tools by Gemini CLI.

Available tools:

## 1. Symbol Search

```bash
kit symbol <query> --json
```

Returns matching code symbols plus relevant documentation hits.

Example:

```bash
kit symbol write_memory --json
```

Use this before opening files to discover definitions and narrow search scope.

## 2. Call Graph Lookup

```bash
kit callers <symbol> --json
```

Returns locations that call the given symbol.

Example:

```bash
kit callers write_memory --json
```

Use this to understand usage relationships before reading larger files.

## 3. Code Snippet Retrieval

```bash
kit snippet <path>:<line> --json
```

Returns a small contextual code snippet around a specific location.

Example:

```bash
kit snippet runtime/kernel.py:120 --json
```

Use this only after a concrete path and line number are known.

## Recommended Workflow

1. Call `kit symbol` before opening large files.
2. Use `kit callers` to narrow investigation scope.
3. Call `kit snippet` only after you know the exact file location.

This keeps context small, reduces token usage, and treats `kit` as the stable query surface for code navigation.
