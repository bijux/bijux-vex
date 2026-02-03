# Determinism Matrix (Storage × Execution)

This matrix is normative. It defines determinism, auditability, and experimental status for each storage/execution combination.

| Storage | Execution | Deterministic? | Auditable? | Experimental? | Notes |
| --- | --- | --- | --- | --- | --- |
| Memory | Exact | Yes | Yes | No | Fully deterministic; replay must match bit-for-bit. |
| Memory | ANN | No (bounded) | Yes | Yes | Requires randomness profile + budgets; replay is envelope-based. |
| VDB (external) | Exact | No by default | Only if adapter proves it | Yes (future) | Not implemented in v0.2; requires explicit opt-in + adapter contract. |
| VDB (external) | ANN | No (bounded) | Only if adapter proves it | Yes (future) | Not implemented in v0.2; explicit opt-in required. |

## Determinism rules
- “Deterministic” means **bit-identical replay** under the same contract.
- “Auditable” means provenance is emitted and replay/compare are legal under declared bounds.
- Any VDB path is **non-default** and must be explicitly selected.
