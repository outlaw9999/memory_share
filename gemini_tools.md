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

## 4. Unified Context

```bash
kit context <symbol> --json
```

Returns the best matching definition, callers, callees, a local snippet, related docs, and lightweight metrics.

Example:

```bash
kit context write_memory --json
```

Use this when you want the full picture in one tool call.

## 5. Related Symbols

```bash
kit related <symbol> --json
```

Returns nearby symbols for exploration: similar names, direct callers, direct callees, and same-file peers.

Example:

```bash
kit related write_memory --json
```

Use this after `kit context` when you want to explore adjacent APIs, refactor targets, or local module patterns.

## Recommended Workflow

1. Call `kit context` first when you already know the target symbol.
2. Fall back to `kit symbol` when you need discovery or disambiguation.
3. Use `kit related` when you need nearby APIs, module peers, or alternate entry points.
4. Use `kit callers` for wider impact analysis beyond the default context window.
5. Call `kit snippet` only after you need more local code than `kit context` returns.

This keeps context small, reduces token usage, and treats `kit` as the stable query surface for code navigation.
