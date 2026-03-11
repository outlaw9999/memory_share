# Agent Kernel Memory Architecture Blueprint

## 1. 4-Tier Memory Pipeline (The "Cognitive Context" Stack)
**Layer 1: Session Memory (Ephemeral Stream)**
- **Purpose**: Tracks immediate conversation context, hypotheses, and temporary reasoning traces.
- **TTL**: tied to the active active working block/task.
- **Why**: Prevents the agent from re-evaluating the same dead-end twice during a specific session.

**Layer 2: Symbol Memory (Synaptic Bridges)**
- **Purpose**: Facts, bug notes, direct architectural decisions.
- **Attached to**: `symbols` via the `bridges` table.
- **Why**: "When I look at `verify_token`, I see *why* and *how* it was designed."

**Layer 3: Skill Memory (Procedural Workflows)**
- **Purpose**: Step-by-step debug workflows, analysis procedures.
- **Triggered by**: Symbol + Intent (e.g., `login fail`).
- **Why**: Automates the "how to approach this specific localized problem" without relying on the LLM to guess the right steps.

**Layer 4: Pattern Memory (Global Heuristics)**
- **Purpose**: Repository-wide rules, architectural invariants, code smells.
- **Attached to**: Sub-graphs or motifs (e.g., "Any DB write must use a context manager").
- **Why**: Automates project-wide style, structure, and design principles.

## 2. The Hybrid Symbol Resolver (kit/core/grounding.py)
This is the core engine that shifts `.kit` from a naive search to a deterministic structure.

**The 5-Stage Grounding Flow:**
1.  **Intent / Keyword Extraction**: Extract the action and the subject (e.g., "why does `login` fail").
2.  **Symbol Candidate Search (FTS5 + Fuzzy)**: Find `login_user`, `AuthService.login`, etc.
3.  **Graph Expansion (Graph Slice)**: Fetch the immediate local graph (callers, callees) for the top candidates via `kit/core/graph_slice_engine.py` (ATLAS logic graph).
4.  **Pattern & Skill Trigger Evaluation**: Identify if the local sub-graph matches any known `motifs` or `skills`. (e.g., this is a "db-related module", attach DB debug skills).
5.  **Context Synthesis**: Package the Symbol, Slice, specific Symbol Memories, and triggered Skills/Patterns into the `CognitiveContext` payload for the MCP `signal`/`summary` responses.

## 3. Database Schema Recommendations (`neural_memory.db`)

We must expand the current simple `neurons` / `bridges` schema. 
*Note: SQLite must be used with Foreign Keys enabled.*

```sql
-- Existing Tables
CREATE TABLE IF NOT EXISTS neurons (...); 

-- Expanded Bridge Table (Supporting Multiple Targets)
CREATE TABLE IF NOT EXISTS bridges (
    bridge_id TEXT PRIMARY KEY,
    symbol_id TEXT NOT NULL,         -- Links to atlas.db -> symbols.rowid
    target_type TEXT NOT NULL,       -- 'neuron', 'skill', 'pattern'
    target_id TEXT NOT NULL,         -- fk to respective table
    weight REAL DEFAULT 1.0,         -- Graph Relevance / Bridge Weight
    confidence REAL DEFAULT 0.8,
    status TEXT DEFAULT 'active'     -- 'active' | 'orphan'
);

-- New Layers
CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    triggers_json TEXT NOT NULL,     -- e.g., ["login fail", "auth error"]
    steps_json TEXT NOT NULL,        -- The procedural steps
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    motif_signature TEXT,            -- Sub-graph matching motif
    resolution_json TEXT             -- The heuristic / rule
);
```

## 4. The Path Forward
To implement this cleanly, we should:
1.  **Draft `kit/core/grounding.py`**: Start building the `HybridSymbolResolver`. This replaces the naive search and introduces the multi-stage weighting logic ($Score = w_1 \cdot match + \dots$). We'll mock the new memory tables initially.
2.  **Update `BrainV2Adapter` (`kit/adapters/memory_adapter.py`)**: Expand the adapter to query not just `neurons`, but also `skills` and `patterns` via the updated `bridges` schema.
3.  **Update `CognitiveRouter` (`kit/services/cognitive_router.py`)**: Assemble the `CognitiveBundle` by fusing the logic slice with the expanded semantic memory layers.
4.  **Expose via MCP (`kit_mcp_server.py`)**: Ensure `kit_skill_run` returns this richer `CognitiveContext` to the LLM agent. 

*Optional Future Step: The **Experience Distiller** - An asynchronous watcher that reviews session logs (Layer 1) and promotes successful workflows into `skills` (Layer 3).*
