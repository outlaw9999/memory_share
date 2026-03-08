# Agent Bootstrap Guide

Follow these 5 steps to initialize reasoning over this codebase.

### 1. Environment Detection
Check for the presence of `kit.py` and the ATLAS database at `.antigravity/atlas/atlas.db`.
```bash
python kit.py --version
```

### 2. Global Health Check
Run the "Doctor" query to understand the general state of the codebase.
```sql
-- See docs/ADVANCED_AGENT_QUERIES.md for the 'Kit Doctor' SQL
```

### 3. Architecture Context
Infer the system layers to build a mental map of the project.
```sql
-- See docs/ADVANCED_AGENT_QUERIES.md for 'Hidden Architecture Inference'
```

### 4. Risk Assessment
Analyze hotspots by combining Git churn with graph centrality.
```bash
git log --name-only --since="2 weeks ago" # Use this to feed the churn JSON
```

### 5. Impact Analysis
Before suggesting any change, run a semantic impact query to identify the blast radius.
```bash
python kit.py impact <symbol_name> --depth 2
```
