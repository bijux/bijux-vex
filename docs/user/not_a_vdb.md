# bijux-vex is not a vector DB

- No storage contract: the execution ledger is provenance, not a database.
- No serving guarantees: latency/availability are not SLAs; budgets are for experiments.
- No CRUD API beyond fixtures and ingestion for execution.
- Determinism and nondeterminism are **execution contracts**, not storage modes.
- If you need multi-tenant vector storage, pick a vector DB and use bijux-vex for audited execution only.
- ANN replay is not promised: ND executions record envelopes and audit; replay validates envelopes, not ANN equality.
