# AGENT PLAYBOOK
> **CRITICAL INSTRUCTION FOR ALL AI AGENTS**: You must strictly follow this playbook when working in this repository. 
> This repository uses `.kit` as its Cognitive OS Layer. DO NOT rely solely on your LLM context window.

## 1. Before Coding (Context Hydration)
Always check the cognitive memory before proposing architectural changes or writing new implementations:
```bash
kit recall --here
```
*Read the output to understand invariants, decisions, and preferences specific to the directory you are working in.*

## 2. When Making Decisions
If you and the human mutually agree on an architectural choice, design pattern, or project rule, you MUST record it so future agents remember:
```bash
kit learn --tag decision "We use SQLite FTS5 for all text search instead of Vector DBs."
```
*Use `--tag invariant` for hard rules, `--tag decision` for architectural choices, and `--tag preference` for stylistic choices.*

## 3. Before Committing (Governance Check)
You are NOT allowed to blindly run `git commit`. You must pass the cognitive preflight check first:
```bash
kit preflight -m "feat(auth): add JWT validation logic"
```
*If `kit preflight` returns a WARNING or BLOCK, you have violated an architectural memory constraint. You must fix your code or explain to the human why the rule should be changed.*

## 4. If Blocked by Preflight
If your code is blocked:
1. Revise your implementation to comply with the cognitive memory.
2. OR, if the architecture is officially changing, work with the human to run `kit learn` to supersede the old rule.

## ⛔ NEVER DO THESE
- **NEVER** commit without running `kit preflight`.
- **NEVER** ignore `invariant` facts returned by `kit recall`.
- **NEVER** assume a dependency or framework is allowed without checking the memory first.
