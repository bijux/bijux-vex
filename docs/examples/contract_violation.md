# Contract violation example

This shows a minimal invariant failure and the exact error raised.

## Scenario
- Artifact built for deterministic execution.
- Request attempts non-deterministic execution without ANN support.

## Command
```sh
bijux vex execute --artifact-id exact --vector [0,1,0] --top-k 1 --contract non_deterministic
```

## Expected result
- Execution is rejected with `NDExecutionUnavailableError`.
- Error message: `Non-deterministic execution requested without ANN support`.
- Provenance/audit records the failure; no execution occurs.

## Why it is forbidden
- Non-deterministic execution requires an ANN backend to honor the contract.
- Silent fallback to deterministic would violate declared execution semantics.
- ND execution is **stable_bounded** at the contract level but still experimental in behavior; refusal without ANN keeps the contract honest.
- Error message is stable and public: `Non-deterministic execution requested without ANN support`.
