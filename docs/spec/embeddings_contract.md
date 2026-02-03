# Embedding Generation Contract

Embedding generation is a **contracted step**, not a hidden side-effect.
It may be deterministic or non-deterministic, but it must always surface provenance.

## Rules
- Embedding generation must be explicitly invoked; no implicit embedding creation.
- Deterministic embeddings must be reproducible under a declared model/version.
- Non-deterministic embeddings must declare randomness sources and bounds.

## Provenance requirements
Every embedding step must emit the following metadata (see provenance schema extension):
- `embedding_source`
- `embedding_determinism`
- `embedding_seed`
- `embedding_model_version`

## Status
No embedding generation is implemented in v0.2.0. This document defines the contract for future work.
