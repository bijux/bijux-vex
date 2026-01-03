# OpenAPI v1 normative examples

These payloads are normative; changing them is a breaking API change.

## Execute (deterministic)
```json
{
  "vector": [0.0, 1.0],
  "top_k": 3,
  "execution_contract": "deterministic",
  "execution_intent": "exact_validation"
}
```

## Execute (non_deterministic, ANN)
```json
{
  "vector": [0.0, 1.0],
  "top_k": 3,
  "execution_contract": "non_deterministic",
  "execution_intent": "exploratory_search",
  "execution_mode": "bounded",
  "execution_budget": { "max_ann_probes": 10, "max_error": 0.2 },
  "randomness_profile": { "seed": 1, "sources": ["ann_graph"] }
}
```

## Compare
```json
{
  "artifact_id": "exact",
  "other_artifact_id": "ann"
}
```
