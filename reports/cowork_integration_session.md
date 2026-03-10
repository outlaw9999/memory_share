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

A persistent ED25519 SSH key was generated for Claude Cowork to authenticate with GitHub in future sessions.

- **Key type:** ed25519
- **Label:** `cowork-claude-outlaw9999`
- **Private key location:** `.ssh/id_ed25519` (in selected workspace folder)
- **Public key:**

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOezqyOSLmAeFd6AvsDh6nLOsVfPWEmGp1KvQBYeqhJp cowork-claude-outlaw9999
```

> Add this public key to GitHub → Settings → SSH Keys to enable future passwordless push.

---

### 2. Brain Update Workflow via Cowork

The Cowork agent can now serve as a brain sync operator:

1. User triggers update in chat ("push brain update")
2. Agent reads existing brain files from repo (public layer only)
3. Agent synthesizes a session update document (no personal data)
4. Agent commits + pushes to `memory_share` via SSH or PAT
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
    └── layer3_metadata_schema.md
```

Brain V2 phases 1–3 are complete. No Phase 4 defined yet.

---

## Open Questions / Next Steps

- [ ] Add SSH public key to GitHub account to enable future key-based push
- [ ] Define Phase 4 scope (e.g., cross-session memory injection into Cowork context)
- [ ] Consider `layer2_core` update workflow: can Cowork agent write to private layer before push?
- [ ] Evaluate whether session documents like this one belong in `reports/` or a new `sessions/` folder

---

## Privacy Compliance

This document contains no personal data, private Layer 2 notes, stream logs, or SQLite records.
Safe to publish in `memory_share`.
