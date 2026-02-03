# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from bijux_vex.infra.plugins.contract import PluginContract
from bijux_vex.infra.plugins.entrypoints import load_entrypoints


@dataclass(frozen=True)
class EmbeddingMetadata:
    provider: str
    model: str
    model_version: str | None
    embedding_determinism: str | None
    embedding_seed: int | None
    embedding_device: str | None
    embedding_dtype: str | None
    config_hash: str


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[tuple[float, ...]]
    metadata: EmbeddingMetadata


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    def embed(
        self, texts: list[str], model: str, options: Mapping[str, str] | None = None
    ) -> EmbeddingBatch:
        raise NotImplementedError


EmbeddingProviderFactory = Callable[[], EmbeddingProvider]


class EmbeddingProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, tuple[EmbeddingProviderFactory, PluginContract]] = {}
        self._default: str | None = None

    def register(
        self,
        name: str,
        *,
        factory: EmbeddingProviderFactory,
        contract: PluginContract,
        default: bool = False,
    ) -> None:
        if not contract.determinism:
            raise ValueError("Embedding provider contract must declare determinism")
        if contract.randomness_sources is None:
            raise ValueError(
                "Embedding provider contract must declare randomness sources"
            )
        key = name.lower()
        self._providers[key] = (factory, contract)
        if default:
            self._default = key

    def resolve(self, name: str | None = None) -> EmbeddingProvider:
        key = (name or self._default or "").lower()
        if not key:
            raise ValueError("Embedding provider name is required")
        if key not in self._providers:
            raise ValueError(f"Unknown embedding provider: {name}")
        factory, _contract = self._providers[key]
        return factory()

    def providers(self) -> list[str]:
        return sorted(self._providers.keys())

    @property
    def default(self) -> str | None:
        return self._default


EMBEDDING_PROVIDERS = EmbeddingProviderRegistry()


def _register_sentence_transformers() -> None:
    try:
        from bijux_vex.infra.embeddings.sentence_transformers import (
            SentenceTransformersProvider,
        )
    except Exception:
        return

    EMBEDDING_PROVIDERS.register(
        "sentence_transformers",
        factory=SentenceTransformersProvider,
        contract=PluginContract(
            determinism="model_dependent",
            randomness_sources=("model_init", "runtime_device"),
            approximation=False,
        ),
        default=True,
    )


_register_sentence_transformers()
load_entrypoints("bijux_vex.embeddings", EMBEDDING_PROVIDERS)


__all__ = [
    "EmbeddingMetadata",
    "EmbeddingBatch",
    "EmbeddingProvider",
    "EmbeddingProviderRegistry",
    "EMBEDDING_PROVIDERS",
]
