# SDR (Software Design Review) Test Scenarios

These scenarios are designed to verify that an AI Agent can leverage `.kit` v1.0.0 semantic intelligence to make safe architectural decisions.

---

## Scenario 1: The "Blast Radius" Audit
**Context**: You need to refactor the `Scanner.parse` method in `plugins/atlas_indexer/scanner.py`.
**Agent Task**:
1. Run `kit impact Scanner.parse --depth 2`.
2. Identify all direct callers and their distribution across modules.
3. Determine if this refactor requires a breaking change notification for the `api` layer.

**Pass Criteria**: Agent correctly identifies that `AtlasIndexer` is the primary caller and determines the risk level for the `api` layer based on the compressed impact JSON.

---

## Scenario 2: The "Layer Violation" Detection
**Context**: A developer has added a direct database call from a UI component.
**Agent Task**:
1. Run the `Architecture Guard` query from `docs/ADVANCED_AGENT_QUERIES.md`.
2. Detect if any symbol in the `ui` module is calling a symbol in the `db` or `storage` modules.
3. Block the PR if a violation is detected.

**Pass Criteria**: Agent identifies the specific file and line where the layer violation occurs and cites the `docs/ARCHITECTURE_FREEZE.md` as the authority.

---

## Scenario 3: The "Hotspot" Risk Analysis
**Context**: You receive a PR that modifies `core/engine.py`.
**Agent Task**:
1. Run `kit doctor` to check general system health.
2. Run the `Risk Hotspot Detector` query using recent git churn data.
3. If `core/engine.py` is identified as a high-centrality hotspot with high churn, increase the review scrutiny and suggest extra unit tests.

**Pass Criteria**: Agent recognizes `core/engine.py` as a critical "hub" and correctly weights the risk using both graph centrality and git history.

---

## Scenario 4: The "Circular Dependency" Cleanup
**Context**: You are tasked with improving maintainability.
**Agent Task**:
1. Run the `Cycle Detection` query.
2. If any cycles are found (e.g., `api -> core -> db -> api`), propose a decoupling strategy.
3. Verify that the proposed solution would break the cycle in the graph.

**Pass Criteria**: Agent identifies the exact modules involved in the cycle and provides a valid architectural rationale for breaking it.
