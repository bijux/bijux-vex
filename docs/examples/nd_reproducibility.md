# Non-deterministic reproducibility experiment

This walkthrough shows what changes and what stays bounded when running the same ND execution repeatedly.

## Setup

```bash
bijux vex create --name repro
bijux vex ingest --name repro --documents "hi" --vectors "[[0.0, 0.0]]"
bijux vex materialize --name repro --contract non_deterministic --budget-latency 5 --budget-memory 5 --budget-error 0.2
```

## Run the same ND execution 3 times

```bash
for i in 1 2 3; do
  bijux vex execute --name repro --vector "[0.0,0.0]" --top-k 1 \
    --contract non_deterministic --mode bounded \
    --budget-latency 5 --budget-memory 5 --budget-error 0.2 \
    --randomness-seed $i
done
```

### What you should see

- Results may vary in rank/score order, but `ApproximationReport` records:
  - algorithm, version, backend
  - `randomness_sources`, `random_seed`
  - `recall_at_k`, `rank_displacement`, `distance_error`
- Provenance shows the randomness envelope and ND contract.

Sample truncated output (3 runs):

```json
{"approximation":{"algorithm":"hnswlib","rank_displacement":0.0,"recall_at_k":1.0,"random_seed":1},"results":[{"rank":1,"score":0.0,"vector_id":"vec-0"}]}
{"approximation":{"algorithm":"hnswlib","rank_displacement":0.0,"recall_at_k":1.0,"random_seed":2},"results":[{"rank":1,"score":0.0,"vector_id":"vec-0"}]}
{"approximation":{"algorithm":"hnswlib","rank_displacement":0.0,"recall_at_k":1.0,"random_seed":3},"results":[{"rank":1,"score":0.0,"vector_id":"vec-0"}]}
```

### Replay envelope

Replay of ND executions does **not** expect equality. It validates that observed divergence stays within the recorded approximation bounds; otherwise replay fails with a contract violation.
