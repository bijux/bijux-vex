# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
import doctest
from pathlib import Path


def test_determinism_doc_snippets():
    repo_root = Path(__file__).resolve().parents[2]
    doc_path = repo_root / "docs" / "design" / "determinism.md"
    text = doc_path.read_text(encoding="utf-8")
    parser = doctest.DocTestParser()
    test = parser.get_doctest(
        text, {}, name=str(doc_path), filename=str(doc_path), lineno=0
    )
    runner = doctest.DocTestRunner(verbose=False)
    failures, _ = runner.run(test)
    assert failures == 0
