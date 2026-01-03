# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from typing import Any, cast

from bijux_vex.boundaries.pydantic_edges.models import (
    CreateRequest,
    ExecutionArtifactRequest,
    ExecutionRequestPayload,
    ExplainRequest,
    IngestRequest,
)
from bijux_vex.contracts.authz import AllowAllAuthz, Authz, DenyAllAuthz
from bijux_vex.contracts.tx import Tx
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import (
    AuthzDeniedError,
    InvariantError,
    NotFoundError,
    ValidationError,
)
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.core.identity.fingerprints import corpus_fingerprint, vectors_fingerprint
from bijux_vex.core.runtime.execution_plan import ExecutionPlan
from bijux_vex.core.runtime.vector_execution import (
    RandomnessProfile,
    derive_execution_id,
    execution_signature,
)
from bijux_vex.core.types import (
    Chunk,
    Document,
    ExecutionArtifact,
    ExecutionBudget,
    ExecutionRequest,
    Vector,
)
from bijux_vex.domain.execution_requests.compare import compare_executions
from bijux_vex.domain.execution_requests.execute import (
    execute_request,
    start_execution_session,
)
from bijux_vex.domain.provenance.lineage import explain_result
from bijux_vex.domain.provenance.replay import replay
from bijux_vex.infra.adapters.sqlite.backend import sqlite_backend
from bijux_vex.services.policies.id_policy import (
    ContentAddressedIdPolicy,
    IdGenerationStrategy,
)


class Orchestrator:
    # This module is allowed to be “ugly but bounded”: wiring/glue only.
    # Domain rules belong in domain/core; do not reintroduce policy here.
    def __init__(
        self,
        backend: Any | None = None,
        authz: Authz | None = None,
        state_path: str | Path | None = None,
    ) -> None:
        if backend is not None:
            self.backend = backend
        else:
            backend_env = (os.getenv("BIJUX_VEX_BACKEND") or "").lower()
            chosen_raw: str | Path = (
                state_path or os.getenv("BIJUX_VEX_STATE_PATH") or "session.sqlite"
            )
            chosen_path = Path(chosen_raw)
            if backend_env == "memory":
                from bijux_vex.infra.adapters.memory.backend import memory_backend

                self.backend = memory_backend()
            elif backend_env == "hnsw":
                from bijux_vex.infra.adapters.hnsw.backend import hnsw_backend

                self.backend = hnsw_backend(db_path=str(chosen_path))
            else:
                self.backend = sqlite_backend(str(chosen_path))
        if authz is not None:
            self.authz = authz
        else:
            auth_mode = (os.getenv("BIJUX_VEX_AUTHZ_MODE") or "").lower()
            self.authz = (
                DenyAllAuthz() if auth_mode in {"deny", "deny_all"} else AllowAllAuthz()
            )
        ro = (os.getenv("BIJUX_VEX_READ_ONLY") or "").lower()
        self.read_only = ro in {"1", "true", "yes"}
        self.id_policy: IdGenerationStrategy = ContentAddressedIdPolicy()
        self.default_artifact_id = self.id_policy.next_artifact_id()
        self._latest_corpus_fingerprint: str | None = None
        self._latest_vector_fingerprint: str | None = None

    def _tx(self) -> Tx:
        return cast(Tx, self.backend.tx_factory())

    def _guard_mutation(self, action: str) -> None:
        if self.read_only:
            raise AuthzDeniedError(
                message=f"Mutation '{action}' disallowed in read-only mode"
            )

    def _require_artifact(self, artifact_id: str) -> ExecutionArtifact:
        artifact = self.backend.stores.ledger.get_artifact(artifact_id)
        if artifact is None:
            raise NotFoundError(message=f"Execution artifact {artifact_id} not found")
        return cast(ExecutionArtifact, artifact)

    def list_artifacts(self) -> dict[str, Any]:
        artifacts = tuple(self.backend.stores.ledger.list_artifacts())
        return {"artifacts": [a.artifact_id for a in artifacts]}

    def capabilities(self) -> dict[str, Any]:
        caps = getattr(self.backend.stores, "capabilities", None)
        if caps is None:
            return {
                "backend": getattr(self.backend, "name", "unknown"),
                "contracts": [],
                "deterministic_query": None,
                "supports_ann": False,
                "replayable": None,
                "metrics": [],
                "max_vector_size": None,
                "isolation_level": None,
            }
        return {
            "backend": getattr(self.backend, "name", "unknown"),
            "contracts": sorted(
                c.value if hasattr(c, "value") else str(c)
                for c in (caps.contracts or [])
            ),
            "deterministic_query": caps.deterministic_query,
            "supports_ann": bool(
                caps.supports_ann if caps.supports_ann is not None else caps.ann_support
            ),
            "replayable": caps.replayable,
            "metrics": sorted(caps.metrics or []),
            "max_vector_size": caps.max_vector_size,
            "isolation_level": caps.isolation_level,
        }

    def create(self, req: CreateRequest) -> dict[str, Any]:
        self._guard_mutation("create")
        return {"name": req.name, "status": "created"}

    def ingest(self, req: IngestRequest) -> dict[str, Any]:
        self._guard_mutation("ingest")
        with self._tx() as tx:
            for idx, doc_text in enumerate(req.documents):
                doc_id = self.id_policy.document_id(doc_text)
                doc = Document(document_id=doc_id, text=doc_text)
                self.authz.check(tx, action="put_document", resource="document")
                self.backend.stores.vectors.put_document(tx, doc)
                chunk = Chunk(
                    chunk_id=self.id_policy.chunk_id(doc.document_id, 0),
                    document_id=doc.document_id,
                    text=doc_text,
                    ordinal=0,
                )
                self.authz.check(tx, action="put_chunk", resource="chunk")
                self.backend.stores.vectors.put_chunk(tx, chunk)
                vec = Vector(
                    vector_id=self.id_policy.vector_id(
                        chunk.chunk_id, tuple(req.vectors[idx])
                    ),
                    chunk_id=chunk.chunk_id,
                    values=tuple(req.vectors[idx]),
                    dimension=len(req.vectors[idx]),
                )
                self.authz.check(tx, action="put_vector", resource="vector")
                self.backend.stores.vectors.put_vector(tx, vec)
        self._latest_corpus_fingerprint = corpus_fingerprint(req.documents)
        self._latest_vector_fingerprint = vectors_fingerprint(req.vectors)
        return {"ingested": len(req.documents)}

    def materialize(self, req: ExecutionArtifactRequest) -> dict[str, Any]:
        self._guard_mutation("materialize")
        existing = self.backend.stores.ledger.get_artifact(self.default_artifact_id)
        if existing and existing.execution_contract is not req.execution_contract:
            raise InvariantError(
                message="Cannot rebuild artifact with different execution contract"
            )
        artifact = ExecutionArtifact(
            artifact_id=self.default_artifact_id,
            corpus_fingerprint=self._latest_corpus_fingerprint
            or corpus_fingerprint(()),
            vector_fingerprint=self._latest_vector_fingerprint
            or vectors_fingerprint(()),
            metric="l2",
            scoring_version="v1",
            schema_version="v1",
            execution_contract=req.execution_contract,
            build_params=(),
        )
        plan = ExecutionPlan(
            algorithm="exact_vector_execution",
            contract=req.execution_contract,
            k=0,
            scoring_fn=artifact.metric,
            randomness_sources=(),
            reproducibility_bounds="bit-identical",
        )
        execution_id = derive_execution_id(
            request=ExecutionRequest(
                request_id="materialize",
                text=None,
                vector=None,
                top_k=0,
                execution_contract=req.execution_contract,
                execution_intent=ExecutionIntent.EXACT_VALIDATION,
                execution_mode=(
                    ExecutionMode.STRICT
                    if req.execution_contract is ExecutionContract.DETERMINISTIC
                    else ExecutionMode.BOUNDED
                ),
                execution_budget=(
                    ExecutionBudget()
                    if req.execution_contract is ExecutionContract.NON_DETERMINISTIC
                    else None
                ),
            ),
            backend_id=getattr(self.backend, "name", "unknown"),
            algorithm="exact_vector_execution",
            plan=plan,
        )
        artifact = replace(
            artifact,
            execution_plan=plan,
            execution_signature=execution_signature(
                plan, artifact.corpus_fingerprint, artifact.vector_fingerprint, None
            ),
            execution_id=execution_id,
        )
        with self._tx() as tx:
            self.authz.check(tx, action="put_artifact", resource="artifact")
            self.backend.stores.ledger.put_artifact(tx, artifact)
        return {
            "artifact_id": artifact.artifact_id,
            "execution_contract": artifact.execution_contract.value,
            "replayable": artifact.replayable,
        }

    def execute(self, req: ExecutionRequestPayload) -> dict[str, Any]:
        if req.vector is None:
            raise ValidationError(message="execution vector required")
        artifact_id = req.artifact_id
        if artifact_id is None:
            available = tuple(self.backend.stores.ledger.list_artifacts())
            if len(available) == 1:
                artifact_id = available[0].artifact_id
            else:
                raise ValidationError(message="artifact_id required for execution")
        artifact = self._require_artifact(artifact_id)
        if artifact.execution_contract is not req.execution_contract:
            raise InvariantError(
                message="Execution contract does not match artifact execution contract"
            )
        randomness_budget = None
        if req.execution_budget:
            randomness_budget = {
                key: value
                for key, value in {
                    "max_latency_ms": req.execution_budget.max_latency_ms,
                    "max_memory_mb": req.execution_budget.max_memory_mb,
                    "max_error": req.execution_budget.max_error,
                }.items()
                if value is not None
            }
        randomness_profile = (
            RandomnessProfile(
                seed=req.randomness_profile.seed,
                sources=tuple(req.randomness_profile.sources or ()),
                bounded=req.randomness_profile.bounded,
                budget=randomness_budget if randomness_budget else None,
                envelopes=tuple(
                    (k, float(v))
                    for k, v in (randomness_budget or {}).items()
                    if isinstance(v, (int, float))
                ),
            )
            if req.randomness_profile
            else None
        )
        if (
            req.execution_contract is ExecutionContract.NON_DETERMINISTIC
            and req.randomness_profile is None
        ):
            raise ValidationError(
                message="randomness_profile required for non_deterministic execution"
            )
        request = ExecutionRequest(
            request_id="req-1",
            text=req.request_text,
            vector=tuple(req.vector),
            top_k=req.top_k,
            execution_contract=req.execution_contract,
            execution_intent=req.execution_intent,
            execution_mode=req.execution_mode,
            execution_budget=ExecutionBudget(
                max_latency_ms=req.execution_budget.max_latency_ms
                if req.execution_budget
                else None,
                max_memory_mb=req.execution_budget.max_memory_mb
                if req.execution_budget
                else None,
                max_error=req.execution_budget.max_error
                if req.execution_budget
                else None,
            ),
        )
        session = start_execution_session(
            artifact,
            request,
            self.backend.stores,
            randomness=randomness_profile,
            ann_runner=getattr(self.backend, "ann", None),
        )
        execution_result, results = execute_request(
            session,
            self.backend.stores,
            ann_runner=getattr(self.backend, "ann", None),
        )
        with self._tx() as tx:
            self.backend.stores.ledger.put_execution_result(tx, execution_result)
            updated_artifact = replace(
                artifact,
                execution_plan=execution_result.plan,
                execution_signature=execution_result.signature,
                execution_id=execution_result.execution_id,
            )
            self.backend.stores.ledger.put_artifact(tx, updated_artifact)
            artifact = updated_artifact
        return {
            "results": [r.vector_id for r in results],
            "execution_contract": artifact.execution_contract.value,
            "replayable": artifact.replayable,
            "execution_id": execution_result.execution_id,
        }

    def explain(self, req: ExplainRequest) -> dict[str, Any]:
        art_id = req.artifact_id
        if art_id is None:
            artifacts = tuple(self.backend.stores.ledger.list_artifacts())
            if len(artifacts) == 1:
                art_id = artifacts[0].artifact_id
            else:
                raise ValidationError(message="artifact_id required to explain result")
        artifact = self._require_artifact(art_id)
        request = ExecutionRequest(
            request_id="req-1",
            text=None,
            vector=(0.0, 0.0),
            top_k=10,
            execution_contract=artifact.execution_contract,
            execution_intent=ExecutionIntent.EXACT_VALIDATION,
            execution_mode=ExecutionMode.STRICT,
        )
        with self._tx():
            session = start_execution_session(
                artifact,
                request,
                self.backend.stores,
                ann_runner=getattr(self.backend, "ann", None),
            )
            exec_result, results_iter = execute_request(
                session,
                self.backend.stores,
                ann_runner=getattr(self.backend, "ann", None),
            )
            results = list(results_iter)
        target = next((r for r in results if r.vector_id == req.result_id), None)
        if target is None:
            raise InvariantError(message="result not found")
        data = explain_result(target, self.backend.stores)
        document = cast(Document, data["document"])
        chunk = cast(Chunk, data["chunk"])
        vector = cast(Vector, data["vector"])
        artifact_meta = cast(ExecutionArtifact, data["artifact"])
        return {
            "document_id": document.document_id,
            "chunk_id": chunk.chunk_id,
            "vector_id": vector.vector_id,
            "artifact_id": artifact_meta.artifact_id,
            "metric": artifact_meta.metric,
            "score": target.score,
            "execution_contract": artifact_meta.execution_contract.value,
            "replayable": artifact_meta.replayable,
            "execution_id": exec_result.execution_id,
        }

    def replay(
        self,
        request_text: str,
        expected_contract: ExecutionContract | None = None,
        artifact_id: str | None = None,
    ) -> dict[str, Any]:
        chosen_artifact_id = artifact_id
        if chosen_artifact_id is None:
            artifacts = tuple(self.backend.stores.ledger.list_artifacts())
            if len(artifacts) == 1:
                chosen_artifact_id = artifacts[0].artifact_id
            else:
                raise ValidationError(message="artifact_id required for replay")
        artifact = self._require_artifact(chosen_artifact_id)
        if expected_contract and expected_contract is not artifact.execution_contract:
            raise InvariantError(
                message="Replay contract does not match artifact execution contract"
            )
        request = ExecutionRequest(
            request_id="req-replay",
            text=request_text,
            vector=(0.0, 0.0),
            top_k=5,
            execution_contract=artifact.execution_contract,
            execution_intent=ExecutionIntent.REPRODUCIBLE_RESEARCH,
            execution_mode=ExecutionMode.STRICT
            if artifact.execution_contract is ExecutionContract.DETERMINISTIC
            else ExecutionMode.BOUNDED,
            execution_budget=ExecutionBudget(
                max_latency_ms=10, max_memory_mb=10, max_error=1.0
            )
            if artifact.execution_contract is ExecutionContract.NON_DETERMINISTIC
            else None,
        )
        outcome = replay(
            request,
            artifact,
            self.backend.stores,
            ann_runner=getattr(self.backend, "ann", None),
        )
        return {
            "matches": outcome.matches,
            "original_fingerprint": outcome.original_fingerprint,
            "replay_fingerprint": outcome.replay_fingerprint,
            "details": outcome.details,
            "nondeterministic_sources": outcome.nondeterministic_sources,
            "execution_contract": artifact.execution_contract.value,
            "replayable": artifact.replayable,
            "execution_id": outcome.execution_id,
        }

    def compare(
        self,
        req: ExecutionRequestPayload,
        artifact_a_id: str | None = None,
        artifact_b_id: str | None = None,
    ) -> dict[str, object]:
        if req.vector is None:
            raise ValidationError(message="execution vector required for comparison")
        art_a = self._require_artifact(artifact_a_id or self.default_artifact_id)
        art_b = self._require_artifact(artifact_b_id or self.default_artifact_id)
        vector_values = tuple(req.vector)
        if (
            req.execution_contract is ExecutionContract.NON_DETERMINISTIC
            and req.randomness_profile is None
        ):
            raise ValidationError(
                message="randomness_profile required for non_deterministic execution"
            )

        def _as_request(artifact: ExecutionArtifact) -> ExecutionRequest:
            return ExecutionRequest(
                request_id=f"compare-{artifact.artifact_id}",
                text=req.request_text,
                vector=vector_values,
                top_k=req.top_k,
                execution_contract=artifact.execution_contract,
                execution_intent=req.execution_intent,
                execution_mode=req.execution_mode,
                execution_budget=ExecutionBudget(
                    max_latency_ms=req.execution_budget.max_latency_ms
                    if req.execution_budget
                    else None,
                    max_memory_mb=req.execution_budget.max_memory_mb
                    if req.execution_budget
                    else None,
                    max_error=req.execution_budget.max_error
                    if req.execution_budget
                    else None,
                ),
            )

        req_a = _as_request(art_a)
        req_b = _as_request(art_b)
        ann_runner = getattr(self.backend, "ann", None)
        session_a = start_execution_session(
            art_a, req_a, self.backend.stores, ann_runner=ann_runner
        )
        session_b = start_execution_session(
            art_b, req_b, self.backend.stores, ann_runner=ann_runner
        )
        exec_a, res_a = execute_request(
            session_a, self.backend.stores, ann_runner=ann_runner
        )
        exec_b, res_b = execute_request(
            session_b, self.backend.stores, ann_runner=ann_runner
        )
        diff = compare_executions(exec_a, res_a, exec_b, res_b)
        return {
            "execution_a": diff.execution_a.execution_id,
            "execution_b": diff.execution_b.execution_id,
            "overlap_ratio": diff.overlap_ratio,
            "recall_delta": diff.recall_delta,
            "rank_instability": diff.rank_instability,
        }
