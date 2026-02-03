# ND Examples With Interpretation

## Example: Good ND run

- Metrics: low instability, strong distance margin, low entropy.
- Confidence: high.
- Action: safe for recommendations, still record provenance.

## Example: Unstable ND run

- Metrics: high instability, low margin.
- Confidence: low.
- Action: enable witness mode or switch to deterministic for verification.

## Example: Refusal

- Reason: budget too tight for requested recall.
- Action: increase latency budget or lower target recall.
