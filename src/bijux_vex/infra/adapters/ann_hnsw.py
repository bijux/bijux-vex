# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from typing import Any

try:  # pragma: no cover - optional dependency
    import hnswlib
except Exception:  # pragma: no cover - optional dependency
    hnswlib = None

from bijux_vex.infra.adapters.ann_reference import ReferenceAnnRunner


class HnswAnnRunner(ReferenceAnnRunner):
    """Production HNSW ANN runner backed by hnswlib."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if hnswlib is None:  # pragma: no cover - optional dependency
            raise RuntimeError("hnswlib is required for HnswAnnRunner")
        super().__init__(*args, **kwargs)


__all__ = ["HnswAnnRunner"]
