# ND Troubleshooting

Low recall

- Increase `nd.target_recall` or use `accurate` profile.
- Enable witness mode to validate quality.

High latency

- Reduce candidate limits or use `fast` profile.
- Lower `top_k` if possible.

Unstable results

- Provide an explicit seed.
- Ensure index hash and parameters are stable across runs.

Backend unavailable

- Check `bijux vex vdb status`.
- Verify backend installation and credentials.

Index drift

- Rebuild the ND index.
- Ensure corpus fingerprint matches the artifact.
