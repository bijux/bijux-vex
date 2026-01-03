# Deterministic replay example

```bash
bijux vex replay --artifact art-1 --contract deterministic
```

Expected:
- Replay uses stored plan + artifact; no live vector source mutation.
- Results match original execution exactly; mismatch raises InvariantError.

Failure example:
- Altered plan fingerprint ⇒ replay refused.
