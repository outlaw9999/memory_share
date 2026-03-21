# Skill: kit-workflow-v1
Description: The Golden Cognitive Workflow for .kit Ecosystem (v1.2.3+)

This is the MANDATORY daily workflow for interacting with the .kit memory system. All autonomous agents and human developers MUST adhere to these 4 cognitive triggers to maintain zero memory drift.

## 1. Cognitive Friction (Coding & Debugging)
- When encountering a bug or anomaly: MUST pipe the error into `kit learn --auto` to log the friction.
- When resolving a bug: MUST cement the outcome using `kit learn --tag decision`.

## 2. Deep Thinking (Ideation & Architecture)
- ALWAYS draft complex thoughts or rules in a local `.md` file within the IDE.
- Ingest into the cognitive engine via standard pipeline: `cat rule.md | kit learn --auto`.

## 3. Context Retrieval (Memory Loss)
- When context is lost or before starting a new task, NEVER hallucinate. 
- MUST query the brain first: `kit recall <keyword>`.

## 4. Governance Guard (Committing)
- NEVER push code without verifying architectural invariants.
- MUST run the cognitive preflight check: `kit preflight -m "<commit message>"`.
