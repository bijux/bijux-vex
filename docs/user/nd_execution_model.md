# ND Execution Model Explained

ND (non-deterministic) execution is an **explicit** mode with declared randomness, bounded quality, and refusal when bounds are violated.

ND planning

- Selects a runner based on capabilities and configuration.
- Resolves parameters from explicit profiles or tuning output.
- Applies budgets and refusal rules before execution.

Runner selection

- The system chooses the best available ND runner.
- If no runner can satisfy the requested capabilities, ND refuses.

Parameters and budgets

- Parameters are explicit or resolved from profiles.
- Budgets bound latency, memory, and candidate exploration.

Degradation and refusal

- ND may degrade only through explicit policies.
- If bounds are exceeded or determinism rules are violated, ND refuses.

This model maps directly to the NDExecutionModel stages: plan, execute, verify, and postprocess.
