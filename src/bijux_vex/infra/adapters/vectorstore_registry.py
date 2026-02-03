# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from bijux_vex.core.errors import BackendCapabilityError, ValidationError
from bijux_vex.infra.adapters.vectorstore import VectorStoreAdapter
from bijux_vex.infra.plugins.contract import PluginContract
from bijux_vex.infra.plugins.entrypoints import load_entrypoints


@dataclass(frozen=True)
class VectorStoreDescriptor:
    name: str
    available: bool
    supports_exact: bool
    supports_ann: bool
    deterministic_exact: bool
    experimental: bool
    notes: str | None = None
    version: str | None = None


@dataclass(frozen=True)
class VectorStoreResolution:
    descriptor: VectorStoreDescriptor
    adapter: VectorStoreAdapter
    uri_redacted: str | None


class NoOpVectorStoreAdapter(VectorStoreAdapter):
    backend = "memory"
    is_noop = True

    def connect(self) -> None:
        return None

    def insert(
        self,
        vectors: Iterable[Sequence[float]],
        metadata: Iterable[dict[str, Any]] | None = None,
    ) -> list[str]:
        if metadata:
            return [entry.get("vector_id", "") for entry in metadata]
        return []

    def query(
        self, vector: Sequence[float], k: int, mode: str
    ) -> list[tuple[str, float]]:
        return []

    def delete(self, ids: Iterable[str]) -> int:
        return 0


VectorStoreFactory = Callable[
    [str | None, Mapping[str, str] | None], VectorStoreAdapter
]
AvailabilityCheck = Callable[[], tuple[bool, str | None, str | None]]


def _redact_uri(uri: str | None) -> str | None:
    if uri is None:
        return None
    parts = urlsplit(uri)
    if not parts.scheme or not parts.netloc:
        return uri
    userinfo, _, host = parts.netloc.rpartition("@")
    if not userinfo:
        return uri
    username, _, _password = userinfo.partition(":")
    redacted_userinfo = f"{username}:***" if username else "***"
    return urlunsplit(
        (
            parts.scheme,
            f"{redacted_userinfo}@{host}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


class VectorStoreRegistry:
    def __init__(self) -> None:
        self._entries: dict[
            str,
            tuple[
                VectorStoreDescriptor,
                VectorStoreFactory,
                AvailabilityCheck | None,
                PluginContract,
            ],
        ] = {}

    def register(
        self,
        name: str,
        *,
        descriptor: VectorStoreDescriptor,
        factory: VectorStoreFactory,
        contract: PluginContract,
        availability: AvailabilityCheck | None = None,
    ) -> None:
        key = name.lower()
        if not contract.determinism:
            raise ValueError("Plugin contract must declare determinism")
        if contract.randomness_sources is None:
            raise ValueError("Plugin contract must declare randomness sources")
        self._entries[key] = (descriptor, factory, availability, contract)

    def resolve(
        self,
        name: str,
        uri: str | None = None,
        options: Mapping[str, str] | None = None,
    ) -> VectorStoreResolution:
        if not name:
            raise ValidationError(message="vector store name is required")
        raw = name.lower()
        key = raw[4:] if raw.startswith("vdb:") else raw
        if key not in self._entries:
            raise ValidationError(
                message=(
                    "What happened: unknown vector store backend.\n"
                    f"Why: '{name}' is not registered.\n"
                    "How to fix: choose a backend listed in `bijux vex capabilities` or install the plugin.\n"
                    "Where to learn more: docs/spec/vectorstore_adapter.md"
                )
            )
        descriptor, factory, availability, _contract = self._entries[key]
        available = descriptor.available
        version = descriptor.version
        notes = descriptor.notes
        if availability is not None:
            available, version, notes = availability()
        if not available:
            hint = f" (install extras for {descriptor.name})" if descriptor.name else ""
            raise BackendCapabilityError(
                message=(
                    "What happened: vector store backend unavailable.\n"
                    f"Why: '{descriptor.name}' could not be loaded{hint}.\n"
                    "How to fix: install the matching extras and retry.\n"
                    "Where to learn more: docs/spec/vectorstore_adapter.md"
                )
            )
        resolved_descriptor = VectorStoreDescriptor(
            name=descriptor.name,
            available=True,
            supports_exact=descriptor.supports_exact,
            supports_ann=descriptor.supports_ann,
            deterministic_exact=descriptor.deterministic_exact,
            experimental=descriptor.experimental,
            notes=notes,
            version=version,
        )
        adapter = factory(uri, options)
        try:
            adapter.connect()
        except Exception as exc:
            raise BackendCapabilityError(
                message=(
                    "What happened: failed to connect to vector store.\n"
                    f"Why: backend '{descriptor.name}' raised {exc}.\n"
                    "How to fix: verify the URI/options and backend installation.\n"
                    "Where to learn more: docs/spec/failure_semantics.md"
                )
            ) from exc
        return VectorStoreResolution(
            descriptor=resolved_descriptor,
            adapter=adapter,
            uri_redacted=_redact_uri(uri),
        )

    def descriptors(self) -> list[VectorStoreDescriptor]:
        items: list[VectorStoreDescriptor] = []
        for _, (descriptor, _factory, availability, _contract) in sorted(
            self._entries.items()
        ):
            available = descriptor.available
            version = descriptor.version
            notes = descriptor.notes
            if availability is not None:
                available, version, notes = availability()
            items.append(
                VectorStoreDescriptor(
                    name=descriptor.name,
                    available=available,
                    supports_exact=descriptor.supports_exact,
                    supports_ann=descriptor.supports_ann,
                    deterministic_exact=descriptor.deterministic_exact,
                    experimental=descriptor.experimental,
                    notes=notes,
                    version=version,
                )
            )
        return items


VECTOR_STORES = VectorStoreRegistry()


def _noop_factory(
    uri: str | None, options: Mapping[str, str] | None
) -> VectorStoreAdapter:
    return NoOpVectorStoreAdapter()


VECTOR_STORES.register(
    "memory",
    descriptor=VectorStoreDescriptor(
        name="memory",
        available=True,
        supports_exact=True,
        supports_ann=False,
        deterministic_exact=True,
        experimental=False,
        notes="no-op adapter; uses local vector source",
    ),
    factory=_noop_factory,
    contract=PluginContract(
        determinism="deterministic_exact",
        randomness_sources=(),
        approximation=False,
    ),
)
VECTOR_STORES.register(
    "sqlite",
    descriptor=VectorStoreDescriptor(
        name="sqlite",
        available=True,
        supports_exact=True,
        supports_ann=False,
        deterministic_exact=True,
        experimental=False,
        notes="alias for local storage (no-op adapter)",
    ),
    factory=_noop_factory,
    contract=PluginContract(
        determinism="deterministic_exact",
        randomness_sources=(),
        approximation=False,
    ),
)


def _faiss_available() -> tuple[bool, str | None, str | None]:
    try:
        import faiss

        return True, getattr(faiss, "__version__", None), None
    except Exception:
        return False, None, "faiss-cpu not installed"


def _faiss_factory(
    uri: str | None, options: Mapping[str, str] | None
) -> VectorStoreAdapter:
    from bijux_vex.infra.adapters.faiss.adapter import FaissVectorStoreAdapter

    return FaissVectorStoreAdapter(uri=uri, options=options)


VECTOR_STORES.register(
    "faiss",
    descriptor=VectorStoreDescriptor(
        name="faiss",
        available=False,
        supports_exact=True,
        supports_ann=False,
        deterministic_exact=True,
        experimental=True,
        notes="local FAISS index (IndexFlatL2)",
    ),
    factory=_faiss_factory,
    contract=PluginContract(
        determinism="deterministic_exact",
        randomness_sources=(),
        approximation=False,
    ),
    availability=_faiss_available,
)

load_entrypoints("bijux_vex.vectorstores", VECTOR_STORES)


__all__ = [
    "VectorStoreDescriptor",
    "VectorStoreResolution",
    "VectorStoreRegistry",
    "VECTOR_STORES",
    "NoOpVectorStoreAdapter",
]
