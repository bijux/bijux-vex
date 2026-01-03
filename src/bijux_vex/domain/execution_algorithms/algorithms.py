# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Iterable

from bijux_vex.contracts.resources import VectorSource
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import InvariantError, ValidationError
from bijux_vex.core.runtime.vector_execution import RandomnessProfile, VectorExecution
from bijux_vex.core.types import ExecutionArtifact, ExecutionRequest, Result, Vector
from bijux_vex.domain.execution_algorithms.base import (
    VectorExecutionAlgorithm,
    register_algorithm,
)
from bijux_vex.domain.execution_requests import scoring
from bijux_vex.infra.adapters.ann_base import AnnExecutionRequestRunner


class ExactVectorExecutionAlgorithm(VectorExecutionAlgorithm):
    name = "exact_vector_execution"
    supported_contracts = {ExecutionContract.DETERMINISTIC}

    def plan(
        self,
        artifact: ExecutionArtifact,
        request: ExecutionRequest,
        backend_id: str,
    ) -> VectorExecution:
        if artifact.execution_contract is not request.execution_contract:
            raise InvariantError(
                message="Execution contract does not match artifact execution contract",
                invariant_id="INV-010",
            )
        return VectorExecution(
            request=request,
            contract=request.execution_contract,
            backend_id=backend_id,
            algorithm=self.name,
            parameters=(("metric", artifact.metric), ("top_k", request.top_k)),
            randomness=None,
        )

    def execute(
        self,
        execution: VectorExecution,
        artifact: ExecutionArtifact,
        vectors: VectorSource,
    ) -> Iterable[Result]:
        request = execution.request
        if request.vector is None:
            raise ValidationError(
                message="execution vector required", invariant_id="INV-020"
            )
        query_vec = request.vector
        scored: list[Result] = []
        for vector in vectors.list_vectors():
            vector = _ensure_tuple(vector)
            if len(query_vec) != vector.dimension:
                continue
            score = scoring.score(artifact.metric, query_vec, vector.values)
            chunk = vectors.get_chunk(vector.chunk_id)
            document_id = chunk.document_id if chunk else ""
            scored.append(
                Result(
                    request_id=request.request_id,
                    document_id=document_id,
                    chunk_id=vector.chunk_id,
                    vector_id=vector.vector_id,
                    artifact_id=artifact.artifact_id,
                    score=score,
                    rank=0,
                )
            )
        scored.sort(key=scoring.tie_break_key)
        limited = scored[: request.top_k]
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


class ApproximateAnnAlgorithm(VectorExecutionAlgorithm):
    name = "ann_approximate"
    supported_contracts = {ExecutionContract.NON_DETERMINISTIC}

    def __init__(self, runner: AnnExecutionRequestRunner):
        self.runner = runner

    def plan(
        self,
        artifact: ExecutionArtifact,
        request: ExecutionRequest,
        backend_id: str,
    ) -> VectorExecution:
        if artifact.execution_contract is not request.execution_contract:
            raise InvariantError(
                message="Execution contract does not match artifact execution contract",
                invariant_id="INV-010",
            )
        self.runner.ensure_contract(artifact)
        surface = RandomnessProfile(
            sources=tuple(self.runner.randomness_sources),
            bounded=False,
        )
        return VectorExecution(
            request=request,
            contract=request.execution_contract,
            backend_id=backend_id,
            algorithm=self.name,
            parameters=(("top_k", request.top_k),),
            randomness=surface,
        )

    def execute(
        self,
        execution: VectorExecution,
        artifact: ExecutionArtifact,
        vectors: VectorSource,
    ) -> Iterable[Result]:
        if getattr(self.runner, "force_fallback", False):
            return self.runner.deterministic_fallback(
                artifact.artifact_id, execution.request
            )
        return self.runner.approximate_request(artifact, execution.request)


def build_ann_algorithm(runner: AnnExecutionRequestRunner) -> ApproximateAnnAlgorithm:
    algo = ApproximateAnnAlgorithm(runner)
    register_algorithm(algo)
    return algo


def register_algorithms() -> None:
    register_algorithm(ExactVectorExecutionAlgorithm())


def _ensure_tuple(vector: Vector) -> Vector:
    if isinstance(vector.values, tuple):
        return vector
    return Vector(
        vector_id=vector.vector_id,
        chunk_id=vector.chunk_id,
        values=tuple(vector.values),
        dimension=vector.dimension,
        model=vector.model,
    )


register_algorithms()

__all__ = [
    "ExactVectorExecutionAlgorithm",
    "ApproximateAnnAlgorithm",
    "build_ann_algorithm",
]
