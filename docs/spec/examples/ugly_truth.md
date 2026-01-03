# Limitations and failure modes (descriptive)

Scenario: ND ANN execution with budget exhaustion, approximation, provenance, and replay mismatch.

Steps (CLI narrative):
1. `bijux vex materialize --contract non_deterministic`
2. `bijux vex execute --vector ... --contract non_deterministic --budget max-ann-probes=1`
3. Execution returns PARTIAL with `BudgetExceededError` provenance and `DeterminismReport`.
4. Ledger stores `ExecutionResult` + artifact signature.
5. `bijux vex replay --contract non_deterministic` → mismatch allowed but recorded; `ReplayOutcome.details` carries divergence and randomness sources.
6. `bijux vex compare --exact artifact-A --approx artifact-B` → overlap/recall deltas highlight approximation loss.

What it proves:
- Budgets abort mid-plan, not post-hoc.
- ND replay is legal but must declare divergence.
- Provenance is required; replay without ledger state fails fast.
- Approximation is auditable, not silent.
