# Determinism Refusal Guide

Deterministic execution refuses when guarantees cannot be met. These refusals are intentional and protect correctness.

Common refusal reasons

- `backend_capability_missing`: The selected backend does not support deterministic exact.
- `determinism_violation`: A requested mode or component is non-deterministic.
- `index_mismatch`: Index hash or parameters do not match the artifact.
- `randomness_required`: ND-only randomness was requested under deterministic contract.

Example refusal payload

```json
{
  "error": {
    "reason": "determinism_violation",
    "message": "[INV-203] What happened: deterministic execution requested with ANN index.\nWhy: ANN is non-deterministic.\nHow to fix: use exact index or switch to ND contract.\nWhere to learn more: docs/user/determinism_refusals.md",
    "remediation": "Use exact mode or explicitly request ND with bounds."
  }
}
```

How to resolve

- Use an exact backend and exact index mode.
- Remove ANN-only flags.
- Rebuild artifacts to match the expected configuration.

When override is allowed

- Deterministic refusals are not overridable. If you need approximation, use ND explicitly.
