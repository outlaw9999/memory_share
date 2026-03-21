# AGENT PLAYBOOK

This playbook defines the working rules for AI agents operating in this repository.

## Operating limits

1. Max autonomous attempts on the same problem: `5`
2. If progress stalls after 5 attempts, stop and surface the blocker to the human
3. Before stopping, persist a short summary with `kit learn`
4. Do not run silent background loops for more than 30 minutes without updating memory or progress

## Authority order

- Generated `.kit/context` and `AGENTS.md` content are the canonical local source of truth
- If narrative docs conflict with generated manifests, prefer the generated manifests
- Tag authority is strict: `invariant > decision > preference > note`
- Lower-authority memories cannot override higher-authority memories

## Required memory behavior

- Use `kit learn --supersede <id>` when intentionally replacing an older fact
- Treat `HIGH_CONFIDENCE` memories as authoritative context
- Treat `AMBIGUOUS` memories as cautionary context
- Treat `WEAK_SIGNAL` memories as optional guidance, not hard rules
- Treat `EMPTY` as no usable memory context

## Governance behavior

- Use `kit reflect` before risky edits when drift is likely
- Respect `kit preflight` as a hard gate for invariant violations
- Do not hide invariant conflicts or invent override authority
- Do not silently ignore failures while writing canonical manifests or memory state

## Resilience behavior

- Prefer healthy providers selected by the router
- Capacity failures should fall back immediately instead of retrying the same provider blindly
- Use `kit doctor --check-agents` for visibility into persisted agent metrics
- Use `kit doctor --reset-cloud` when cloud provider cooldown state needs recovery

## Unix-Philosophy Locked

Goal: preserve the Unix and Linux design posture of `.kit` and `kit-agent` so new agents and developers can understand the system quickly and operate it safely.

1. Single responsibility

- `.kit` is the deterministic memory kernel.
- `kit-agent` is the orchestration, routing, fallback, and prompt-injection layer.
- Do not expand the stable line into vector search, ANN retrieval, or automatic invariant conflict merging.

2. Text streams and composability

- The CLI is stream-first: stdin in, stdout out.
- Commands must compose cleanly with shell tools and automation.
- Example: `git diff | kit learn --tag decision --content "..."`.

3. Determinism and predictability

- Identical inputs should yield identical ranked context.
- Compute-at-write keeps retrieval bounded and predictable.
- Arbitration order is strict: `invariant > decision > preference > note`.
- Assessment states are `HIGH_CONFIDENCE`, `AMBIGUOUS`, `WEAK_SIGNAL`, and `EMPTY`.

4. Immutable and traceable memory

- The ledger is append-only.
- `superseded_at` is used for soft-prune and dedupe instead of hidden deletion.
- Lineage and overrides must remain explicit and reviewable.

5. Explicit non-goals and scope lock

- No semantic inference beyond explicit metadata and deterministic scoring.
- No embeddings, ANN indexes, or vector retrieval.
- No auto-resolution of invariant conflicts.
- No product-surface expansion beyond the locked AMSB v1.2.0 GA scope.

6. Safe multi-agent concurrency

- SQLite WAL mode is the concurrency backbone.
- Writes use bounded retries and immediate locking discipline.
- Recovery paths stay explicit through `kit doctor --check-agents` and `kit doctor --reset-cloud`.

7. Stable API surface

- `kit.api` remains the stable integration boundary: `learn()`, `recall()`, `recall_with_assessment()`, `reflect()`, `preflight_check()`, and `export_prompt()`.
- CLI and API behavior should stay aligned and deterministic.

8. Memory hygiene and knowledge distillation (v1.2.3)

- Runtime noise such as `task_*` and test-only facts should not dominate manifests.
- Duplicate facts should be soft-deduped by `uid + content + tag + scope + symbol`.
- `.kit/context` and `AGENTS.md` should expose distilled signal, not raw historical clutter.
- **[NEW]** Key distilled facts currently include `preflight_pipe`, `cli_unicode`, `recall_binding`, and `prompt_contract`.
- **[NEW]** Prefer `legacy` tag for mass ingestion of historical facts to maintain chronological and structural purity.

9. Verification and storm-proofing

- Unit, integration, behavioral, storm, and chaos tests define the release contract.
- Manifest and memory should reflect architectural truth directly, without requiring git archaeology.

10. ASCII and encoding safety

- CLI output should stay ASCII-safe across Windows and Unix-like consoles.
- Generated `.kit/context` and `AGENTS.md` content should remain encoding-safe.
- Preflight and recall-adjacent pipelines must accept piped stdin when used in automation.

11. Auto-Routing Protocol (v1.2.3 upgrade)

Agents SHOULD prefer `kit learn --auto` for routine observations to invoke the v1.2.3 Governance Pipeline:

1. **Heuristic Sanitization**: The system will automatically drop transient chatter and block high-entropy secrets.
2. **Deterministic Grading**: Facts are scored on a scale of 0.0 to 1.0. 
   - `Score > 0.85`: Promoted to GLOBAL.
   - `Score <= 0.85`: Confined to LOCAL.
3. **No Inference**: Auto-routing is based on deterministic heuristics and scoring, NOT semantic LLM inference. The agent remains responsible for the accuracy of the `--content`.
