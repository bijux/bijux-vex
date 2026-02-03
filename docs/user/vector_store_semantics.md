# Vector Store Semantics

Vector stores are adapters with explicit capabilities. Bijux-Vex does not assume database semantics.

Exact vs ANN

- Exact search is deterministic and replayable.
- ANN is ND and must declare randomness and bounds.

Delete semantics

- Deletes must be persisted or explicitly refused.
- If a backend cannot guarantee delete semantics, the operation fails.

Rebuild and compaction

- Some backends require rebuild after deletes.
- Compaction is explicit and never implicit.

Consistency guarantees

- Local stores are typically read-after-write consistent.
- Remote stores may be eventual; this is recorded in capabilities and provenance.

Backend differences

- FAISS: local, fast, exact and ANN depending on index type.
- Qdrant: remote, supports filters and ANN, may be eventual.
- Memory/SQLite: deterministic exact only.
