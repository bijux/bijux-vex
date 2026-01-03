# ANN execution example

```bash
bijux vex execute --contract non_deterministic --intent exploratory_search --vector "[0.3,0.4]" --budget.max_ann_probes 10
```

Expected:
- ANN algorithm selected, randomness sources recorded
- ApproximationReport persisted with recall/rank displacement
- DeterminismReport present with reproducibility bounds

Failure example:
- Missing budget or randomness profile ⇒ invariant failure before execution.
