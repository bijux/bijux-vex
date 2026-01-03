# Non-deterministic execution with audit

```bash
bijux vex execute --contract non_deterministic --vector "[0.5,0.6]" --budget.max_latency_ms 50 --budget.max_ann_probes 20
```

Expected:
- RandomnessProfile captured (seed, sources, bounded flag, budget).
- DeterminismReport includes randomness sources and reproducibility bounds.
- ApproximationReport shows recall and displacement; status may be PARTIAL if budgets trigger.

Failure example:
- Missing randomness profile or budget triggers invariant failure; execution does not start.
