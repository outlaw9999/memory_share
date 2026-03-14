# Skill: Kit Architecture Audit (kit_audit)
# Version: 1.0.0
# Description: Cognitive audit of the codebase architecture using .kit engine and Stones.

## 🎯 Goal
Provide a "Principal Engineer" level review of the codebase by combining raw graph diagnostics with semantic reasoning.

## 🛠️ Tools & Input
1. **`kit doctor`**: Raw report of architectural violations (Layer A -> Layer B).
2. **SQL Stones**:
   - `hotspots.sql`: Identified high-risk/high-coupling symbols.
   - `cycles.sql`: Circular dependencies detection.
   - `choke_points.sql`: Critical bottlenecks.
   - `slice_impact.sql`: Reachability analysis for core changes.

## 🧠 Reasoning Workflow
1. **Diagnostic Gathering**:
   - Run `kit doctor --json` to get the baseline violation count.
   - Execute `kit query hotspots` to find the most coupled components.
   - Execute `kit query cycles` to ensure the graph is a DAG where required.

2. **Semantic Fusion**:
   - Compare the current **Code Graph** state with the **Memory Graph** (`brain/` and `AGENT_CONTEXT.md`).
   - Identify **Memory Drift**: Does the code implement patterns that contradict documented architectual decisions?

3. **Risk Assessment**:
   - Categorize issues into: `Critical Architecture Breach`, `Technical Debt`, `Performance Bottleneck`.

4. **Prescription**:
   - Provide a natural language summary of the system's health.
   - Suggest 3 concrete refactoring steps to reduce violations.

## 📋 Report Template
```markdown
# 🩺 Kit Architecture Audit Report

## 📊 High-Level Metrics
- **Violations**: [N]
- **Cyclic Dependencies**: [YES/NO]
- **Core Hotspots**: [Symbols]

## 🔍 Cognitive Analysis
[AI reasoning about why these violations exist and their impact on the system's maintainability.]

## ⚠️ Memory Drift Detection
[Detect if code has evolved away from the intended design patterns in the brain/ layer.]

## 🧪 Prescription
1. [Step 1]
2. [Step 2]
3. [Step 3]
```
