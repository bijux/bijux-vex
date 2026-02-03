# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

CLI_HELP = """                                                                                
 Usage: python -m bijux_vex.boundaries.cli.app [OPTIONS] COMMAND [ARGS]...      
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ list-artifacts                                                               │
│ capabilities                                                                 │
│ ingest                                                                       │
│ materialize                                                                  │
│ execute                                                                      │
│ explain                                                                      │
│ replay                                                                       │
│ compare                                                                      │
│ vdb             Vector DB utilities                                          │
╰──────────────────────────────────────────────────────────────────────────────╯

"""


def test_cli_help_is_frozen():
    repo_root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    out = subprocess.check_output(
        [sys.executable, "-m", "bijux_vex.boundaries.cli.app", "--help"],
        text=True,
        env=env,
    )
    assert out == CLI_HELP
