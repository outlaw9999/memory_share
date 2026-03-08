# WAL Delivery Model

Status: Phase 6 architecture note

The Antigravity runtime uses an append-only WAL with `intent`, `commit`, and `rollback` records.
The `JournalTailer` emits downstream events only after a matching `commit`.

Pipeline:

```text
journal (WAL)
  ->
tailer
  ->
commit events (`txn_id`, `ts`)
  ->
consumer
  ->
idempotent sink
```

Delivery semantics:

- Transport from WAL to tailer consumers is `at-least-once`.
- Tailer preserves WAL order and does not reorder transactions.
- `txn_id` is the transaction identity for replay-safe downstream processing.
- `ts` is transaction metadata and may be used for diagnostics or anomaly detection.

Consumer contract:

- Consumers must treat `txn_id` as the idempotency key.
- Consumers should record applied transactions before re-applying stateful updates.
- Exactly-once effect is achieved at the sink layer, not by the WAL transport itself.

Non-goals:

- The tailer does not provide exactly-once transport semantics.
- The tailer does not guarantee global logical ordering across independent resources.

This note formalizes the delivery contract expected by Atlas and other downstream plugins.
