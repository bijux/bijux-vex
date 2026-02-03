# Deterministic Execution: End-to-End

Deterministic execution means **exact search, stable ordering, and replayable results**. If any component would violate determinism, the system refuses.

Requirements

- Execution contract: `deterministic`
- Exact-capable backend
- No ND-only features (ANN, approximate filters)

Supported backends

- Memory and SQLite adapters are deterministic exact.
- FAISS exact is deterministic if configured with exact index types.

What breaks determinism

- ANN indices or approximate search.
- Non-deterministic embeddings without explicit declarations.
- Backends that cannot guarantee exact search.

Replay semantics

- Replay is allowed only when fingerprints match.
- Replay is refused when index hash, config hash, or backend signature differs.

CLI example

```bash
bijux vex ingest --doc "hello" --vector "[0.0, 1.0, 0.0]" \
  --vector-store memory

bijux vex materialize --execution-contract deterministic \
  --vector-store memory

bijux vex execute --artifact-id art-1 \
  --execution-contract deterministic --execution-intent exact_validation \
  --execution-mode strict --vector "[0.0, 1.0, 0.0]"
```

API example

```json
POST /execute
{
  "artifact_id": "art-1",
  "vector": [0.0, 1.0, 0.0],
  "top_k": 5,
  "execution_contract": "deterministic",
  "execution_intent": "exact_validation",
  "execution_mode": "strict"
}
```
