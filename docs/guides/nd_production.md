# ND In Production

This guide shows how to run non-deterministic (ND) execution safely and intentionally.

## Choose A Profile

Use an explicit profile to set baseline quality:

```bash
bijux vex execute \
  --execution-contract non_deterministic \
  --execution-intent exploratory_search \
  --execution-mode bounded \
  --randomness-seed 42 \
  --randomness-sources ann_index \
  --nd-profile balanced \
  --vector '[0.1,0.2]' \
  --top-k 5
```

Profiles:
`fast` trades recall for latency,
`balanced` is the default tradeoff,
`accurate` prioritizes recall.

## Set A Recall Target

```bash
--nd-target-recall 0.95
```

If the backend cannot honor the target, the request is refused with a remediation hint.

## Enforce A Latency Budget

```bash
--nd-latency-budget-ms 20
```

When latency exceeds the budget, ND may degrade in a declared ladder:
reduce `k`, switch profile, or refuse.

## Enable Witness Queries

Witness queries sample exact results for auditing.

```bash
--nd-witness-rate 0.1 \
--nd-witness-sample-k 3
```

Witness results are recorded in provenance.

## Read ND Stability Signals

ND results emit stability metrics:

- `rank_instability`
- `distance_margin`
- `similarity_entropy`
- `witness_report`

Use them to validate whether ND is appropriate for your workload.

## Replay Semantics

ND replay is only attempted when a seed is provided:

```bash
--randomness-seed 123
```

If you declare `--randomness-non-replayable`, replay is refused by design.

## Build ANN Indexes Explicitly

Separate index building from query:

```bash
bijux vex materialize --execution-contract non_deterministic --index-mode ann
```

To rebuild:

```bash
bijux vex vdb rebuild --vector-store faiss --mode ann
```

If you need on-demand builds for development, opt in:

```bash
--nd-build-on-demand
```
