# Choosing ND Parameters Without Being an ANN Expert

Use explicit profiles and budgets to control ND behavior safely.

Profiles

- `fast`: minimize latency, lower recall.
- `balanced`: default tradeoff.
- `accurate`: higher recall with more work.

Latency budget

- Use `nd.latency_budget_ms` to bound query time.
- ND refuses if it cannot meet the budget with the chosen profile.

Target recall

- Use `nd.target_recall` when you care about quality.
- If the backend cannot honor the target, ND refuses or degrades with explicit reporting.

When to tune

- Use `bijux vex nd tune` on a representative dataset.
- Apply the recommended config in your `bijux_vex.toml`.

When to refuse

- If you cannot declare a seed or randomness sources.
- If budget and target recall are incompatible.
