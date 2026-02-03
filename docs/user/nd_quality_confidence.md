# ND Quality & Confidence

ND results include quality metrics and a confidence label so downstream systems can act safely.

Quality metrics

- Rank instability: how sensitive the ordering is.
- Distance margin: how separated the top-k neighbors are.
- Similarity entropy: how uniform the scores are.

Witness modes

- `off`: no witness check, metrics reported as not measured.
- `sample`: exact verification on a small subset.
- `full`: exact verification on full candidates.

Confidence labels

- `high_confidence`: stable ranking and clear margins.
- `medium_confidence`: acceptable variance.
- `low_confidence`: unstable or low-signal results.

What to do with low confidence

- Reduce `k` or increase recall targets.
- Enable witness mode.
- Switch to deterministic exact for verification.

Example ND report (simplified)

```json
{
  "quality": {
    "rank_instability": 0.12,
    "distance_margin": 0.45,
    "similarity_entropy": 0.62
  },
  "confidence": "medium_confidence",
  "witness": "sample"
}
```
