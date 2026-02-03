# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from bijux_vex.contracts.resources import ExecutionResources
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import NotFoundError
from bijux_vex.core.types import Result


def explain_result(result: Result, stores: ExecutionResources) -> dict[str, object]:
    document = stores.vectors.get_document(result.document_id)
    if document is None:
        raise NotFoundError(
            message=f"Document {result.document_id} missing for explanation"
        )
    chunk = stores.vectors.get_chunk(result.chunk_id)
    if chunk is None:
        raise NotFoundError(message=f"Chunk {result.chunk_id} missing for explanation")
    vector = stores.vectors.get_vector(result.vector_id)
    if vector is None:
        raise NotFoundError(
            message=f"Vector {result.vector_id} missing for explanation"
        )
    artifact = stores.ledger.get_artifact(result.artifact_id)
    if artifact is None:
        raise NotFoundError(
            message=f"Execution artifact {result.artifact_id} missing for explanation"
        )

    nondeterministic_sources: tuple[str, ...] = ()
    lossy_dimensions: tuple[str, ...] = ()
    execution_contract_status = "stable"
    if artifact.execution_contract is ExecutionContract.NON_DETERMINISTIC:
        nondeterministic_sources = ("approximate_execution",)
        lossy_dimensions = ("ranking",)
        execution_contract_status = "experimental"

    return {
        "document": document,
        "chunk": chunk,
        "vector": vector,
        "artifact": artifact,
        "metric": artifact.metric,
        "score": result.score,
        "execution_contract": artifact.execution_contract,
        "execution_contract_status": execution_contract_status,
        "replayable": artifact.replayable,
        "execution_id": artifact.execution_id,
        "nondeterministic_sources": nondeterministic_sources,
        "lossy_dimensions": lossy_dimensions,
        "embedding_source": vector.model,
        "embedding_determinism": None,
        "embedding_seed": None,
        "embedding_model_version": None,
    }
