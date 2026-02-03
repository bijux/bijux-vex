# Vector Store Opt-In Design (explicit only)

This design prevents silent persistence. Vector store usage must be explicit in both CLI and API.

## CLI
- Flag: `--vector-store <name>`
- No default value.
- CLI must refuse execution or materialization if a vector store is required but not specified.

## API
- Field: `vector_store` in execution/materialization payloads.
- No default value; omission means **no external store**.

## Behavior
- If `vector_store` is set, the adapter is used for persistence/query.
- If `vector_store` is not set, the system uses only the execution ledger and in-memory/vector sources.
- No silent fallback between stores.

## Rationale
- Guarantees that persistence is always explicit.
- Prevents accidental data retention or storage semantics being inferred.
- Aligns with the “Nothing Is Implicit” contract.
