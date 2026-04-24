# AGENTS.md (v1.2.4 CONTRACT)

## CORE PRINCIPLE
Code is source of truth. CLI output and code behavior override docs.

## POLICY BOUNDARY
- AGENTS.md is policy-only.
- Execution routing belongs to code, not markdown.
- Direct execution must not depend on this file at runtime.

## SAFETY INVARIANTS
- Verify before learn when structural or memory integrity is in doubt.
- Use Vantage as the structural sensor for snapshot and verification flows.
- Keep behavior definitions out of docs; keep docs at the constraint level.

## FORBIDDEN
- re-interpreting command routing from docs
- duplicating execution behavior in policy files
- using AGENTS.md as direct-mode execution logic
- rewrite-all
- skip verify
- raw fs edits
