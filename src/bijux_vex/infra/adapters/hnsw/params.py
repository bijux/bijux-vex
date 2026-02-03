# SPDX-License-Identifier: MIT
# Copyright © 2026 Bijan Mousavi
from __future__ import annotations


def resolve_space(metric: str, override: str | None) -> str:
    if override:
        return override
    if metric == "dot":
        return "ip"
    if metric == "cosine":
        return "cosine"
    if metric == "ip":
        return "ip"
    return "l2"


def as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
