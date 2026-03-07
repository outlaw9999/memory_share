# Background Consolidation Policy

## Goal

Phase 3 keeps Layer 3 usable over time without destructive cleanup.

## Current Strategy

The maintenance job classifies each anchor memory into deterministic buckets:

- `promotion_candidate`
- `duplicate`
- `stale_candidate`
- `maintenance_bucket` of `hot`, `warm`, or `cold`

## Rules

### Promotion candidate

A memory may be promoted when:

- it is not marked duplicate
- it is not stale
- it is not private
- it is not a legacy import placeholder

### Duplicate

Duplicates are detected by `content_hash` within the same brain.

- one anchor becomes the canonical record
- all other anchors are tagged as duplicates
- no records are deleted in Phase 3

### Stale candidate

A memory becomes stale when all of these are true:

- age is greater than or equal to `stale_days`
- activation level is below `weak_activation`
- access frequency is below or equal to `weak_access`

Default maintenance thresholds currently use:

- `stale_days = 30`
- `weak_activation = 0.1`
- `weak_access = 1`

## Outputs

The job updates:

- anchor neuron metadata
- anchor fiber metadata and tags
- `brain/layer2_core/maintenance_digest.md`

## Safety

Phase 3 is intentionally non-destructive:

- no anchor neurons are deleted
- no fibers are deleted
- no typed memories are deleted

This keeps rollback simple while still reducing drift through classification and review.
