# Deterministic Replay

Replay verifies that a prior deterministic execution can be reproduced under the same conditions.

When replay is allowed

- Same artifact ID and index hash.
- Same backend signature and parameters.
- Same execution contract and intent.

When replay is refused

- Index hash mismatch.
- Backend version mismatch that invalidates determinism.
- Configuration or parameter drift.

How fingerprints are checked

- Vector fingerprints ensure the corpus is identical.
- Config and algorithm fingerprints ensure the plan matches.
- Backend signature ensures the same deterministic guarantees.

What “matches” means

- Deterministic results must be **bit-identical** and ordered by the canonical query contract.
- Any deviation is reported as a mismatch with a structured refusal.
