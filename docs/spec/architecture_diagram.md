# Architecture diagram (single source)

Textual diagram:

`CLI/API → Orchestrator (glue only) → ExecutionSession (state machine) → ExecutionPlan (immutable) → Algorithm (exact/approx mode) → VectorSource + ANN runner → ExecutionResult + Provenance → Ledger`

Contracts/invariants hit:
- Contract alignment (INV-010) at session start
- Randomness/budget required for ND (INV-020) in planning
- Plan immutability/fingerprint in ExecutionPlan
- Determinism enforcement pre-algorithm selection
- Provenance requirement on replay (INV-040)
- Ledger integrity on persist/replay
