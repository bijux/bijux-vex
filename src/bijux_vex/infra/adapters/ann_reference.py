# SPDX-License-Identifier: MIT
# pyright: reportMissingModuleSource=false, reportMissingImports=false
from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from statistics import mean
from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - optional dependency
    import hnswlib
except ImportError:  # pragma: no cover - optional optional
    hnswlib = None

if TYPE_CHECKING:
    pass

from bijux_vex.contracts.resources import VectorSource
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.core.execution_result import ApproximationReport
from bijux_vex.core.types import ExecutionArtifact, ExecutionRequest, Result
from bijux_vex.infra.adapters.ann_base import AnnExecutionRequestRunner
from bijux_vex.infra.logging import log_event


class ReferenceAnnRunner(AnnExecutionRequestRunner):
    """Deterministic ANN reference runner built on top of a VectorSource."""

    def __init__(self, vectors: VectorSource, index_dir: str | Path | None = None):
        self.vectors = vectors
        self._index: Any | None = None
        self._ids: list[str] = []
        self._index_dir = Path(index_dir) if index_dir else None
        if self._index_dir:
            self._index_dir.mkdir(parents=True, exist_ok=True)
        self._last_query_metadata: dict[str, object] = {}
        if hnswlib is not None:  # runtime sanity for optional dep
            if not hasattr(hnswlib, "Index"):
                raise ImportError("hnswlib missing required attribute Index")
            # Shallow interface contract check to fail fast if stubs drift.
            idx = hnswlib.Index("l2", 2)
            if not hasattr(idx, "knn_query") or not hasattr(idx, "set_ef"):
                raise ImportError("hnswlib Index missing required methods")

    @property
    def randomness_sources(self) -> tuple[str, ...]:
        return ("reference_ann_hnsw",)

    @property
    def reproducibility_bounds(self) -> str:
        return "bounded"

    def approximate_request(
        self, artifact: ExecutionArtifact, request: ExecutionRequest
    ) -> Iterable[Result]:
        if hnswlib is None:
            if request.nd_settings is not None:
                log_event(
                    "nd_backend_downgrade",
                    backend="truncate",
                    reason="hnswlib unavailable",
                )
            return self._truncate_results(artifact, request)
        return self._hnsw_results(artifact, request)

    def deterministic_fallback(
        self, artifact_id: str, request: ExecutionRequest
    ) -> Iterable[Result]:
        return self.vectors.query(artifact_id, request)

    def build_index(
        self, vectors: Iterable[Result], ids: Iterable[str], **params: object
    ) -> None:
        # Index is built lazily during first query; explicit build is a no-op for now.
        return None

    def query(
        self, vector: Iterable[float], k: int, **params: object
    ) -> tuple[list[str], list[float], dict[str, object]]:
        # Use hnswlib when available; fall back to deterministic truncation semantics.
        # Metadata mirrors ANNResultMetadata schema keys.
        if hnswlib is None or self._index is None:
            # build lightweight index from current vectors
            request = ExecutionRequest(
                request_id="ann-query",
                text=None,
                vector=tuple(vector),
                top_k=k,
                execution_contract=ExecutionContract.NON_DETERMINISTIC,
                execution_intent=ExecutionIntent.EXPLORATORY_SEARCH,
                execution_mode=ExecutionMode.BOUNDED,
            )
            stub_artifact = ExecutionArtifact(
                artifact_id="ann-stub",
                corpus_fingerprint="ann-corpus",
                vector_fingerprint="ann-vectors",
                metric="l2",
                scoring_version="v1",
                execution_contract=ExecutionContract.NON_DETERMINISTIC,
            )
            results = list(self._truncate_results(stub_artifact, request))
            return (
                [r.vector_id for r in results],
                [r.score for r in results],
                {
                    "algorithm": "reference_ann_truncation",
                    "index_params": (),
                    "query_params": {"k": k},
                    "n_candidates": len(results),
                    "random_seed": 0,
                    "randomness_source": self.randomness_sources,
                },
            )
        labels: Sequence[Sequence[int]]
        distances: Sequence[Sequence[float]]
        labels, distances = self._index.knn_query([tuple(vector)], k=k)
        return (
            [self._ids[label] for label in labels[0]],
            list(map(float, distances[0])),
            {
                "algorithm": "hnswlib",
                "index_params": {
                    "M": getattr(self, "_m", 8),
                    "ef_search": getattr(self, "_ef_search", 10),
                },
                "query_params": {"k": k},
                "n_candidates": len(labels[0]),
                "random_seed": 0,
                "randomness_source": self.randomness_sources,
            },
        )

    def approximation_report(
        self,
        artifact: ExecutionArtifact,
        request: ExecutionRequest,
        results: Iterable[Result],
    ) -> ApproximationReport:
        materialized = tuple(results)
        exact = tuple(self.deterministic_fallback(artifact.artifact_id, request))
        exact_ids = {res.vector_id: res.rank for res in exact}
        matched = [res for res in materialized if res.vector_id in exact_ids]
        recall = min(1.0, len(matched) / float(request.top_k or 1))
        if matched:
            displacement = mean(
                abs(exact_ids[res.vector_id] - res.rank) for res in matched
            )
        else:
            displacement = float(request.top_k or 1)
        distance_error = 0.0
        if exact:
            exact_scores = {res.vector_id: res.score for res in exact}
            approx_scores = [
                abs(res.score - exact_scores.get(res.vector_id, res.score))
                for res in materialized
            ]
            distance_error = mean(approx_scores) if approx_scores else 0.0
        truncation_ratio = len(materialized) / float(len(exact) or 1)
        return ApproximationReport(
            recall_at_k=recall,
            rank_displacement=displacement,
            distance_error=distance_error,
            algorithm="reference_ann_truncation",
            algorithm_version="v1",
            backend="memory",
            randomness_sources=self.randomness_sources,
            deterministic_fallback_used=False,
            truncation_ratio=truncation_ratio,
            index_parameters=(
                ("backend", "hnswlib" if hnswlib else "truncate"),
                ("ef_search", getattr(self, "_ef_search", None) or 10),
                ("M", getattr(self, "_m", None) or 8),
            ),
            query_parameters=self._query_params_metadata(),
            n_candidates=len(materialized),
            random_seed=self._seed_value(),
        )

    # ---- internals -----------------------------------------------------

    def _truncate_results(
        self, artifact: ExecutionArtifact, request: ExecutionRequest
    ) -> Iterable[Result]:
        results = list(self.vectors.query(artifact.artifact_id, request))
        if not results:
            return ()
        truncated = results[: max(1, len(results) // 2)]
        return truncated

    def _hnsw_results(
        self, artifact: ExecutionArtifact, request: ExecutionRequest
    ) -> Iterable[Result]:
        vectors = list(self.vectors.list_vectors())
        if not vectors:
            return ()
        dim = vectors[0].dimension
        data = []
        ids = []
        for vec in vectors:
            if vec.dimension != dim:
                continue
            data.append(vec.values)
            ids.append(vec.vector_id)
        if not data:
            return ()
        if self._index is None:
            index_file: Path | None = None
            if self._index_dir:
                index_file = self._index_dir / f"{artifact.artifact_id}.hnsw"
                if index_file.exists():
                    index = hnswlib.Index(
                        space="l2" if artifact.metric == "l2" else "ip", dim=dim
                    )
                    index.load_index(str(index_file))
                    self._apply_nd_settings(request)
                    index.set_ef(self._ef_search)
                    self._index = index
                    self._ids = ids
            if self._index is None:
                space = "l2" if artifact.metric == "l2" else "ip"
                index = hnswlib.Index(space=space, dim=dim)
                index.set_seed(0)
                self._apply_nd_settings(request)
                index.init_index(max_elements=len(data), ef_construction=100, M=self._m)
                index.add_items(data, list(range(len(data))))
                index.set_ef(self._ef_search)
            self._index = index
            self._ids = ids
            if self._index_dir and index_file:
                index.save_index(str(index_file))
        query = request.vector or ()
        if len(query) != dim:
            return ()
        self._last_query_metadata = {
            "query_params": {
                "k": request.top_k or 1,
                "ef_search": getattr(self, "_ef_search", 10),
                "nd_profile": getattr(self, "_nd_profile", None),
                "target_recall": getattr(self, "_target_recall", None),
                "latency_budget_ms": getattr(self, "_latency_budget_ms", None),
            },
            "seed": 0,
        }
        labels, distances = self._index.knn_query(
            [query], k=min(request.top_k or 1, len(self._ids))
        )
        results: list[Result] = []
        for rank, (label, dist) in enumerate(
            zip(labels[0], distances[0], strict=True), start=1
        ):
            vec_id = self._ids[label]
            vector = self.vectors.get_vector(vec_id)
            chunk_id = vector.chunk_id if vector else ""
            doc_id = ""
            if vector:
                ch = self.vectors.get_chunk(vector.chunk_id)
                doc_id = ch.document_id if ch else ""
            results.append(
                Result(
                    request_id=request.request_id,
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    vector_id=vec_id,
                    artifact_id=artifact.artifact_id,
                    score=float(dist),
                    rank=rank,
                )
            )
        return tuple(results)

    def _apply_nd_settings(self, request: ExecutionRequest) -> None:
        profile = "balanced"
        target_recall = None
        latency_budget_ms = None
        if request.nd_settings is not None:
            if request.nd_settings.profile:
                profile = request.nd_settings.profile
            target_recall = request.nd_settings.target_recall
            latency_budget_ms = request.nd_settings.latency_budget_ms

        profile_map = {
            "fast": (8, 20),
            "balanced": (16, 50),
            "accurate": (32, 100),
        }
        base_m, base_ef = profile_map.get(profile, (16, 50))

        if target_recall is not None:
            if target_recall >= 0.99:
                base_ef = max(base_ef, 200)
            elif target_recall >= 0.95:
                base_ef = max(base_ef, 100)
            elif target_recall >= 0.9:
                base_ef = max(base_ef, 50)
            else:
                base_ef = max(base_ef, 20)

        applied_ef = base_ef
        if latency_budget_ms is not None:
            if latency_budget_ms < 5:
                applied_ef = min(applied_ef, 20)
            elif latency_budget_ms < 20:
                applied_ef = min(applied_ef, 50)
            if applied_ef < base_ef:
                log_event(
                    "nd_latency_downgrade",
                    requested_ef=base_ef,
                    applied_ef=applied_ef,
                    latency_budget_ms=latency_budget_ms,
                )

        self._m = base_m
        self._ef_search = applied_ef
        self._nd_profile = profile
        self._target_recall = target_recall
        self._latency_budget_ms = latency_budget_ms

    def _query_params_metadata(self) -> tuple[tuple[str, str], ...]:
        params = self._last_query_metadata.get("query_params")
        if isinstance(params, dict):
            return tuple((str(k), str(v)) for k, v in params.items())
        return ()

    def _seed_value(self) -> int | None:
        seed = self._last_query_metadata.get("seed")
        if isinstance(seed, bool):
            return None
        if isinstance(seed, (int, float)):
            return int(seed)
        if isinstance(seed, str):
            try:
                return int(seed)
            except ValueError:
                return None
        return None
