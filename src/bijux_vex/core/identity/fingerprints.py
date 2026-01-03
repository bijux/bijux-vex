# SPDX-License-Identifier: MIT
from __future__ import annotations

from collections.abc import Iterable

from bijux_vex.core.canon import canon
from bijux_vex.core.identity.ids import fingerprint


def corpus_fingerprint(documents: Iterable[str]) -> str:
    """Content-addressed fingerprint of ordered documents."""
    payload = tuple(canon(doc).decode("utf-8") for doc in documents)
    return fingerprint(payload)


def vectors_fingerprint(vectors: Iterable[Iterable[float]]) -> str:
    """Content-addressed fingerprint of ordered vectors."""
    payload = tuple(canon(tuple(vec)).decode("utf-8") for vec in vectors)
    return fingerprint(payload)


__all__ = ["corpus_fingerprint", "vectors_fingerprint"]
