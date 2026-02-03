# What ND Can and Cannot Promise

ND (non-deterministic) execution is designed for speed and scale, not exact replay. It is powerful when you accept trade-offs **explicitly**.

What ND optimizes for

- Fast approximate search at scale.
- Bounded quality with explicit metrics.
- Operational visibility into uncertainty.

What ND cannot guarantee

- Bit-identical replay across runs.
- Exact ranking agreement with deterministic search.
- Stability if index state or parameters drift.

What replaces guarantees

- Quality metrics (instability, margin, entropy).
- Witness checks when enabled.
- Declared randomness profiles and bounds.

ND earns trust by being honest about limits.
