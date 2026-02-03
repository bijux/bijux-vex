# Provenance as an Audit Artifact

Provenance is the audit trail of a vector execution. It explains **what happened**, **why it happened**, and **what was refused**.

Structure

- Inputs: vectors, documents, and configuration.
- Decisions: runner selection, budgets, parameters.
- Randomness: seeds and declared sources.
- Artifacts: index hash, corpus fingerprint, and execution IDs.

How to store

- Treat provenance as immutable audit data.
- Store alongside results and configuration snapshots.

How to compare

- Compare fingerprints to verify deterministic replay.
- Compare ND quality metrics to track stability over time.

Retention strategies

- Keep provenance for all production runs.
- For large volumes, store summaries and reference full artifacts by ID.

How provenance answers “why did this happen?”

- It records the exact plan and parameters used.
- It shows whether any degradation or refusal occurred.
