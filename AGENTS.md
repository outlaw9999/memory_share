# AGENTS.md 

## 🤖 Gemini CLI Sub-Agent Protocol (v1.20.5+)

**CRITICAL RULE: DO NOT USE LEGACY CLI COMMANDS**
As of version 1.20.5, legacy "Command support" (like `/exec` or `/kit` slash commands natively) has been removed. 

### 1. Communication Protocol
- You MUST communicate via **Natural Language + Tool Use** ONLY. 
- State your intent clearly ("I need to query the codebase for X"), and use standard File/Terminal/MCP tools. Do not try to run legacy `/slash` commands directly.

### 2. Available Integration (The `.kit` Architecture Guardian)
- `.kit` provides semantic analysis tools via MCP. Use standard AI tools to interact with `kit_doctor`, `kit_symbol_search`, `kit_skills_list` and `kit_skill_run`.
- Do NOT try to run `kit query ...` through legacy UI commands. If you need terminal execution, use standard `run_command` bash tool explicitly.

### 3. Token Accounting & Memory (Fix 1.20.5)
- The token accounting bug has been resolved. You can now analyze large codebase graphs smoothly without premature context-limit terminations.
- Feel free to load larger slices of context. Memory retention per session has effectively increased by ~15-20%.
- Conversation load times are improved, reducing latency for complex graph topology parsing.

### 4. Code Is Ground Truth
- `.kit` V2 specifies that **code is the ground truth, and memory is the explanation layer**.
- Always verify design documents against the actual codebase. If you detect a divergence, document it as "Architecture Drift".

### 5. Rule Precedence
- This file (`AGENTS.md`) is correctly recognized by Gemini CLI 1.20.5+.
- It defines the new agentic protocol separate from project data payload. Rules here supersede legacy commands in `GEMINI.md`.
