# bijux-vex — vector execution engine with explicit determinism

[![PyPI - Version](https://img.shields.io/pypi/v/bijux-vex.svg)](https://pypi.org/project/bijux-vex/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bijux-vex.svg)](https://pypi.org/project/bijux-vex/)
[![Typing: typed (PEP 561)](https://img.shields.io/badge/typing-typed-4F8CC9.svg)](https://peps.python.org/pep-0561/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/bijux/bijux-vex/raw/main/LICENSES/MIT.txt)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://bijux.github.io/bijux-vex/)
[![CI Status](https://github.com/bijux/bijux-vex/actions/workflows/ci.yml/badge.svg)](https://github.com/bijux/bijux-vex/actions)

bijux-vex executes vector workloads under **contracts**. Deterministic runs are replayable; non-deterministic runs are bounded, audited, and comparable.
Nothing is implicit: no silent defaults, retries, or randomness.

## What bijux-vex is
Vector execution engine with explicit determinism contracts. Deterministic paths are bit-stable and replayable; non-deterministic paths (ANN) are supported but **experimental** and always emit approximation + randomness provenance.

## What bijux-vex is not
- Not a vector DB or storage layer.
- Not an embedding or RAG framework.
- Not a serving platform with SLAs.

## Quick links
- Start here (single onboarding path): [user/start_here.md](user/start_here.md)
- Docs home: https://bijux.github.io/bijux-vex/
- Concepts: [overview/concepts.md](overview/concepts.md)
- API: [api/index.md](api/index.md) and [`api/v1/schema.yaml`](https://github.com/bijux/bijux-vex/blob/main/api/v1/schema.yaml) (canonical contract)
- Examples: [examples/overview.md](examples/overview.md)
- Changelog: [changelog.md](changelog.md)
- Not a vector DB: [user/not_a_vdb.md](user/not_a_vdb.md)

## Reading order (guaranteed)
1) Start with [user/start_here.md](user/start_here.md) for the problem, fit, and next steps.  
2) Then [overview/concepts.md](overview/concepts.md) for execution vs storage and determinism vs non-determinism.  
3) Then [spec/system_contract.md](spec/system_contract.md) and [spec/execution_contracts.md](spec/execution_contracts.md) for the normative rules.  
4) Run [examples/overview.md](examples/overview.md) for deterministic and ANN flows.  
5) Consult [api/index.md](api/index.md) and [`api/v1/schema.yaml`](https://github.com/bijux/bijux-vex/blob/main/api/v1/schema.yaml) when integrating.  
Everything else is reference or maintainer material.

## Start here
Read `docs/user/start_here.md`. It explains the problem, when to use bijux-vex, deterministic vs non-deterministic execution, and where to go next.

## Minimal example (CLI, 10 lines)
```sh
bijux vex create --name demo
bijux vex ingest --documents doc.txt --vectors [[0,1,0]]
bijux vex artifact --artifact-id exact --contract deterministic
bijux vex execute --artifact-id exact --vector [0,1,0] --top-k 1 --contract deterministic
bijux vex artifact --artifact-id ann --contract non_deterministic
bijux vex execute --artifact-id ann --vector [0,1,0] --top-k 1 --contract non_deterministic --randomness-profile seed=1
bijux vex explain --artifact-id exact --result-id <vector_id>
bijux vex compare --artifact-id exact --other-id ann
```

## Execution truth table (canonical)
| Contract | Support level | Replayable | Output stability | Provenance / audit | Notes |
| --- | --- | --- | --- | --- | --- |
| deterministic | stable | yes (bit-identical) | stable | full chain + fingerprints | frozen ABI; breaking changes require major bump |
| non_deterministic | stable_bounded | no (envelope only) | outcome-variable (bounded divergence) | approximation + randomness metadata required | experimental surface; may fail if ANN backend unavailable |

## Stability guarantees
- Supported Python: 3.11–3.13 (CI + metadata aligned).
- Package version: dynamic from git tags via hatch-vcs.
- Public API version: **v1.x** (frozen; breaking changes require major bump).
- Deterministic execution surface and ABI are frozen; breaking changes require a major bump.
- ND/ANN execution is **experimental** and may change; it can legally fail when no ANN backend is available.
- Determinism gates, ANN contracts, and provenance schema are enforced in conformance tests; regressions fail CI.
- Testing policy: tox runs multi-version tests; lint/quality/security/typing gates run only on the lowest supported Python (3.11) for cost/time efficiency.

## No synonym drift
We use one term per concept: **replayable** (deterministic, bit-identical), **audited** (non-deterministic with envelopes), **stable** (supported and frozen), **outcome-variable** (bounded divergence). Avoid “reproducible” or “supported” as stand-ins.

## Public surfaces
- **CLI (Typer)**: `create`, `ingest`, `materialize`, `execute`, `explain`, `replay`, `compare`, `list-artifacts`.
- **API (FastAPI)**: versioned under `bijux_vex.api.v1` with frozen OpenAPI (`api/v1/openapi.v1.json`), endpoints mirror CLI verbs.
- **Core types**: `ExecutionContract`, `ExecutionRequest`, `ExecutionArtifact`, `ExecutionResources`, `ApproximationReport`, `RandomnessProfile`.

## Non-goals checksum
X - Not a VDB or search service.  
X - Not an ML/embedding framework.  
X - Not a serving layer with SLAs.  
X - Not a “best-effort” ANN wrapper—contracts must be explicit.

## Why strict
Aggressive invariants, terminal failures, and refusal to fallback exist to keep provenance honest and prevent silent divergence; permissive modes are intentionally rejected.

## Assumptions
- Trusted runtime and honest backend declaration.  
- Data is non-adversarial unless stated in tests.  
- Users read the “Start here” path before touching API/CLI.

## When contracts are violated
- Deterministic: execution refuses to run; replay fails closed.  
- Non-deterministic: fails fast if ANN unavailable or metadata missing; never silently falls back to deterministic.  
- Budget or capability breaches raise typed errors; no hidden retries or approximations.

## Contributing & release
- Keep invariants terminal; ND without metadata is forbidden.
- Run `make lint quality security test` before any PR.
- Release process: see `docs/maintainer/release_process.md`; tags drive package versions, SBOM, and wheels.
- Licensing: code under MIT; docs/config under CC0. See `docs/legal/licensing.md`.
