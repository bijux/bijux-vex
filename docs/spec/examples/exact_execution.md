# Exact execution example

```bash
bijux vex create
bijux vex ingest --text "hello"
bijux vex materialize --metric l2
bijux vex execute --contract deterministic --vector "[0.1,0.2]"
```

Expected:
- deterministic plan, no randomness sources
- execution artifact with no approximation report
- replay returns identical results

Failure example:
- If backend lacks deterministic support, command fails with InvariantError.
