# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
from bijux_vex.core.execution_intent import ExecutionIntent

from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.types import (
    Chunk,
    Document,
    ExecutionArtifact,
    ExecutionRequest,
    Vector,
)
from bijux_vex.domain.provenance.lineage import explain_result
from bijux_vex.infra.adapters.memory.backend import memory_backend


def test_provenance_contains_only_expected_fields():
    backend = memory_backend()
    doc = Document(document_id="d1", text="hello")
    chunk = Chunk(chunk_id="c1", document_id=doc.document_id, text=doc.text, ordinal=0)
    vec = Vector(
        vector_id="v1", chunk_id=chunk.chunk_id, values=(0.0, 0.0), dimension=2
    )
    artifact = ExecutionArtifact(
        artifact_id="art-1",
        corpus_fingerprint="corp",
        vector_fingerprint="vec",
        metric="l2",
        scoring_version="v1",
        execution_contract=ExecutionContract.DETERMINISTIC,
    )
    with backend.tx_factory() as tx:
        backend.stores.vectors.put_document(tx, doc)
        backend.stores.vectors.put_chunk(tx, chunk)
        backend.stores.vectors.put_vector(tx, vec)
        backend.stores.ledger.put_artifact(tx, artifact)
    result = list(
        backend.stores.vectors.query(
            artifact.artifact_id,
            ExecutionRequest(
                request_id="q1",
                text=None,
                vector=(0.0, 0.0),
                top_k=1,
                execution_contract=ExecutionContract.DETERMINISTIC,
                execution_intent=ExecutionIntent.EXACT_VALIDATION,
            ),
        )
    )[0]
    provenance = explain_result(result, backend.stores)
    assert set(provenance.keys()) == {
        "document",
        "chunk",
        "vector",
        "artifact",
        "metric",
        "score",
        "execution_contract",
        "replayable",
        "execution_id",
        "nondeterministic_sources",
        "lossy_dimensions",
    }
    assert provenance["metric"] == "l2"
    assert provenance["execution_contract"] == ExecutionContract.DETERMINISTIC
    assert provenance["replayable"] is True
