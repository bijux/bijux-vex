# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class VectorStoreConfig:
    backend: str | None = None
    uri: str | None = None
    options: Mapping[str, str] | None = None


@dataclass(frozen=True)
class EmbeddingCacheConfig:
    backend: str | None = None
    uri: str | None = None
    options: Mapping[str, str] | None = None


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str | None = None
    model: str | None = None
    cache: EmbeddingCacheConfig | None = None


@dataclass(frozen=True)
class ExecutionConfig:
    vector_store: VectorStoreConfig | None = None
    embeddings: EmbeddingConfig | None = None


__all__ = [
    "VectorStoreConfig",
    "EmbeddingCacheConfig",
    "EmbeddingConfig",
    "ExecutionConfig",
]
