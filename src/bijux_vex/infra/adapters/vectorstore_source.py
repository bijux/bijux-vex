# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bijux_vex.contracts.resources import VectorSource
from bijux_vex.core.determinism import classify_execution
from bijux_vex.core.errors import ValidationError
from bijux_vex.core.types import Chunk, Document, ExecutionRequest, Result, Vector
from bijux_vex.domain.execution_requests import scoring
from bijux_vex.infra.adapters.vectorstore_registry import VectorStoreResolution


class VectorStoreVectorSource(VectorSource):
    def __init__(self, base: VectorSource, resolved: VectorStoreResolution):
        self._base = base
        self._resolved = resolved
        self._adapter = resolved.adapter

    @property
    def vector_store_metadata(self) -> dict[str, object]:
        index_params = getattr(self._adapter, "index_params", None)
        return {
            "backend": self._resolved.descriptor.name,
            "uri_redacted": self._resolved.uri_redacted,
            "index_params": index_params,
            "supports_exact": self._resolved.descriptor.supports_exact,
            "supports_ann": self._resolved.descriptor.supports_ann,
            "deterministic_exact": self._resolved.descriptor.deterministic_exact,
            "experimental": self._resolved.descriptor.experimental,
        }

    # Document operations
    def put_document(self, tx: Any, document: Document) -> None:
        self._base.put_document(tx, document)

    def get_document(self, document_id: str) -> Document | None:
        return self._base.get_document(document_id)

    def list_documents(self) -> Iterable[Document]:
        return self._base.list_documents()

    def delete_document(self, tx: Any, document_id: str) -> None:
        self._base.delete_document(tx, document_id)

    # Chunk operations
    def put_chunk(self, tx: Any, chunk: Chunk) -> None:
        self._base.put_chunk(tx, chunk)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self._base.get_chunk(chunk_id)

    def list_chunks(self, document_id: str | None = None) -> Iterable[Chunk]:
        return self._base.list_chunks(document_id=document_id)

    def delete_chunk(self, tx: Any, chunk_id: str) -> None:
        self._base.delete_chunk(tx, chunk_id)

    # Vector operations
    def put_vector(self, tx: Any, vector: Vector) -> None:
        self._base.put_vector(tx, vector)
        if getattr(self._adapter, "is_noop", False):
            return
        metadata = {
            "vector_id": vector.vector_id,
            "chunk_id": vector.chunk_id,
            "dimension": str(vector.dimension),
            "model": vector.model or "",
        }
        if vector.metadata:
            if isinstance(vector.metadata, dict):
                items = list(vector.metadata.items())
            else:
                items = list(vector.metadata)
            for key, value in items:
                metadata[str(key)] = str(value)
        self._adapter.insert([list(vector.values)], metadata=[metadata])

    def get_vector(self, vector_id: str) -> Vector | None:
        return self._base.get_vector(vector_id)

    def list_vectors(self, chunk_id: str | None = None) -> Iterable[Vector]:
        return self._base.list_vectors(chunk_id=chunk_id)

    def query(self, artifact_id: str, request: ExecutionRequest) -> Iterable[Result]:
        if request.vector is None:
            raise ValidationError(message="execution vector required")
        if getattr(self._adapter, "is_noop", False):
            return self._base.query(artifact_id, request)
        classify_execution(
            contract=request.execution_contract,
            randomness=None,
            ann_runner=None,
            vector_store=self._resolved.descriptor,
            require_randomness=False,
        )
        results: list[Result] = []
        for vector_id, score in self._adapter.query(
            list(request.vector), request.top_k, mode=request.execution_contract.value
        ):
            vec = self._base.get_vector(vector_id)
            if vec is None:
                continue
            chunk = self._base.get_chunk(vec.chunk_id)
            document_id = chunk.document_id if chunk else ""
            results.append(
                Result(
                    request_id=request.request_id,
                    document_id=document_id,
                    chunk_id=vec.chunk_id,
                    vector_id=vector_id,
                    artifact_id=artifact_id,
                    score=float(score),
                    rank=0,
                )
            )
        results.sort(key=scoring.tie_break_key)
        limited = results[: request.top_k]
        for idx, res in enumerate(limited, start=1):
            limited[idx - 1] = Result(
                request_id=res.request_id,
                document_id=res.document_id,
                chunk_id=res.chunk_id,
                vector_id=res.vector_id,
                artifact_id=res.artifact_id,
                score=res.score,
                rank=idx,
            )
        return limited

    def delete_vector(self, tx: Any, vector_id: str) -> None:
        self._base.delete_vector(tx, vector_id)
        if getattr(self._adapter, "is_noop", False):
            return
        self._adapter.delete([vector_id])


__all__ = ["VectorStoreVectorSource"]
