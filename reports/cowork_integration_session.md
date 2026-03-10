# Cowork Mode Integration — Session Update

**Date:** 2026-03-10
**Session type:** Cowork agent setup + brain sync workflow
**Status:** Active

---

## Context

This document records the first session using Claude Cowork mode to manage brain updates and push them to this repository.

Cowork mode runs Claude as an agentic desktop agent inside a lightweight Linux VM, with access to a persistent workspace folder. It supports file creation, bash execution, and git operations — making it a viable runtime for brain sync tasks.

---

## What Was Established This Session

### 1. SSH Key Setup

A persistent ED25519 SSH key was generated for Claude Cowork to authenticate with GitHub across sessions.

- **Key type:** ed25519
- **Private key location:** `.ssh/id_ed25519` (persisted in workspace folder)
- **Public key:** registered in GitHub account SSH settings

SSH config points `github.com` to this key automatically on each session.

---

### 2. Brain Update Workflow via Cowork

The Cowork agent now serves as the brain sync operator for this repo:

1. User triggers update in chat ("push brain update")
2. Agent reads existing brain files from repo (public layer only)
3. Agent synthesizes a session update document (no personal data)
4. Agent commits + pushes via SSH (no token needed after initial setup)
5. SSH key persists in workspace folder across sessions

This workflow replaces manual brain sync steps and connects the live Cowork context directly to the public memory layer.

---

### 3. Repo Structure Confirmed (as of 2026-03-10)

```
memory_share/
├── README.md
├── SHARE_NOTES.md
├── brain/
│   ├── exports/
│   │   └── neural_memory_architecture.md
│   └── ops/
│       ├── brain_maintenance.py
│       ├── brain_sync_watcher.py
│       ├── layer3_backfill.py
│       ├── layer3_metadata.py
│       ├── query_layer3.py
│       └── search.ps1
└── reports/
    ├── background_consolidation_policy.md
    ├── brain_v2_update_roadmap.md
    ├── brain_state_current.md          ← new: full system state snapshot
    ├── cowork_integration_session.md   ← this file
    └── layer3_metadata_schema.md
```

Brain V2 phases 1–3 are complete. Phase 4 scope is under consideration.

---

## Open Questions / Next Steps

- [ ] Define Phase 4 scope (cross-session memory injection into Cowork context)
- [ ] Consider `layer2_core` update workflow via Cowork agent
- [ ] Evaluate moving session update docs to a dedicated `sessions/` folder

---

## Privacy Compliance

This document contains no personal data, private Layer 2 notes, stream logs, credentials, or SSH key material.
Safe to publish in `memory_share`.
