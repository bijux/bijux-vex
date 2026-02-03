# VectorStoreAdapter (interface contract)

This is the explicit adapter surface for external vector stores. It is **not implemented** in v0.2.0; it exists to make the boundary explicit.

## Interface
Location: `src/bijux_vex/infra/adapters/vectorstore.py`

Methods:
- `connect()`
- `insert(vectors, metadata)`
- `query(vector, k, mode)`
- `delete(ids)`

## Contract notes
- No defaults: adapters must be selected explicitly (see `docs/design/vector_store_opt_in.md`).
- No silent fallbacks: failures are terminal and must surface as explicit errors.
- Adapter implementations are **out of scope** for v0.2.0.
