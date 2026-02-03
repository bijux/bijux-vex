# ND Reproducibility (Honest Version)

ND can be reproducible **within bounds**, but it is not deterministic. Reproducibility depends on index hash, parameters, and randomness declarations.

What can be replayed

- ND executions with explicit seeds and stable index hashes.
- ND runs with replayable bounds declared in provenance.

What cannot be replayed

- Runs without explicit randomness declarations.
- Runs where index hash or parameters drift.

Role of seeds

- If a runner supports seeding, the seed is mandatory for replay.
- If a runner cannot seed, the execution is marked non-replayable.

Index hashes

- ND replay requires matching index hash and corpus fingerprint.
- If hashes differ, replay is refused with a structured payload.

Reproducibility bounds

- ND provenance reports expected overlap or instability bounds.
- These bounds are the contract, not bit-identical equality.
