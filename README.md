# bijux-vex — explicit vector execution

[![PyPI - Version](https://img.shields.io/pypi/v/bijux-vex.svg)](https://pypi.org/project/bijux-vex/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bijux-vex.svg)](https://pypi.org/project/bijux-vex/)
[![Typing: typed (PEP 561)](https://img.shields.io/badge/typing-typed-4F8CC9.svg)](https://peps.python.org/pep-0561/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/bijux/bijux-vex/raw/main/LICENSES/MIT.txt)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://bijux.github.io/bijux-vex/)
[![CI Status](https://github.com/bijux/bijux-vex/actions/workflows/ci.yml/badge.svg)](https://github.com/bijux/bijux-vex/actions)

**What it is**  
Bijux-Vex is a vector execution engine with explicit determinism contracts and provenance.

**Why it’s different**  
Nothing is implicit: persistence, approximation, and randomness require explicit opt-in and are always recorded.

## Quickstart

```bash
python -m bijux_vex.boundaries.cli.app ingest --doc "hello" --vector "[0,1,0]" --vector-store memory
python -m bijux_vex.boundaries.cli.app materialize --execution-contract deterministic --vector-store memory
python -m bijux_vex.boundaries.cli.app execute --vector "[0,1,0]" \
  --execution-contract deterministic \
  --execution-intent exact_validation \
  --vector-store memory
```

## Start Here

- Start here: `docs/user/start_here.md`
- Tutorial: `docs/user/tutorial.md`
- Contracts: `docs/contracts/backward_compatibility.md`, `docs/contracts/implicitness.md`
- Docs home: https://bijux.github.io/bijux-vex/
