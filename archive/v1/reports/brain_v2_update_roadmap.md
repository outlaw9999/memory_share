# Brain V2 Update Roadmap

## Goal

Upgrade the current Antigravity `brain` into a cleaner, safer, and more accurate memory system without losing the strengths of the existing file-first workflow.

## Target State

The target architecture keeps the current three-layer model, but makes each layer stricter:

- `layer1_stream/`: append-only short-term log and episode capture
- `layer2_core/`: block-based shareable operational memory
- `layer2_private/`: local-only personal memory
- `layer3_index/`: semantic + metadata retrieval, with optional graph overlay

## Phase Plan

### Phase 1: Layer 2 Cleanup and Privacy Split

**Work**
- create `layer2_private/`
- split existing core notes into block files
- add frontmatter fields such as `scope`, `privacy`, `owner`, `updated_at`
- define migration rules from legacy files

**Advantages**
- clearer memory ownership
- much safer sharing and Git publishing
- easier handoff between tools and IDEs

**Disadvantages**
- migration work is manual at first
- existing references to old file names may break

**Exit Criteria**
- all core memory files have a defined scope
- personal memory no longer lives inside shareable files

### Phase 2: Layer 3 Metadata and Retrieval Quality

**Work**
- attach metadata to indexed chunks
- filter by project, scope, privacy, and source
- store provenance such as source file and heading
- improve ranking beyond pure semantic similarity

**Advantages**
- higher precision when searching memory
- lower token waste from irrelevant snippets
- easier debugging of why a memory was returned

**Disadvantages**
- schema design becomes more complex
- older indexed data may need re-ingestion

**Exit Criteria**
- every indexed memory record includes stable metadata
- retrieval can be filtered by privacy and project scope

### Phase 3: Background Consolidation

**Work**
- promote important stream notes into core memory
- dedupe repeated chunks
- prune stale or weak memories
- generate compact summaries for long-running work

**Advantages**
- keeps memory usable over long time spans
- avoids unlimited growth of noisy notes
- reduces retrieval drift

**Disadvantages**
- background jobs are harder to debug
- automated promotion can introduce wrong summaries if rules are weak

**Exit Criteria**
- scheduled or manual maintenance can run safely
- long-term memory remains compact and readable

### Phase 4: Graph Overlay and Memory API

**Work**
- model `episode -> entity -> edge`
- add graph-assisted re-ranking
- define a small internal API for add/search/promote/archive
- unify scripts around the same memory interface

**Advantages**
- better recall of relationships between tasks, projects, tools, and decisions
- cleaner future integrations
- more durable architecture for multi-project memory

**Disadvantages**
- highest implementation complexity
- graph schema can become noisy if entity extraction is weak

**Exit Criteria**
- graph layer improves retrieval quality in real tests
- scripts no longer duplicate memory logic

## Recommended Delivery Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4

Do not start the graph layer before Phase 1 is stable.

## Risks

- over-engineering before cleanup
- mixing public and private memory again during migration
- retrieval quality dropping during partial rollout
- maintenance scripts diverging from the actual file structure

## Update Recommendation

### Update Now
- project-local planning workspace
- roadmap and migration design
- privacy split rules

### Update Next
- metadata schema
- improved indexing pipeline
- maintenance automation

### Update Later
- graph overlay
- internal memory API

## Success Definition

The update is successful if the new brain:

- stays file-first and local-first
- is safer to publish and share
- returns better memory with less noise
- remains understandable without needing a complex external platform
