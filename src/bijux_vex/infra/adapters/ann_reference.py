# SPDX-License-Identifier: MIT
# pyright: reportMissingModuleSource=false, reportMissingImports=false
from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from statistics import mean
import time
from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - optional dependency
    import hnswlib
except ImportError:  # pragma: no cover - optional optional
    hnswlib = None

if TYPE_CHECKING:
    pass

from bijux_vex.contracts.resources import VectorSource
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import BudgetExceededError
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.core.execution_result import ApproximationReport
from bijux_vex.core.identity.ids import fingerprint
from bijux_vex.core.types import (
    ExecutionArtifact,
    ExecutionRequest,
    NDSettings,
    Result,
    Vector,
)
from bijux_vex.infra.adapters.ann_base import AnnExecutionRequestRunner
from bijux_vex.infra.logging import log_event


class ReferenceAnnRunner(AnnExecutionRequestRunner):
    """Deterministic ANN reference runner built on top of a VectorSource."""

    def __init__(self, vectors: VectorSource, index_dir: str | Path | None = None):
        self.vectors = vectors
        self._index: Any | None = None
        self._ids: list[str] = []
        self._index_info: dict[str, dict[str, object]] = {}
        self._tuning_samples = 0
        self._k_scale = 1.0
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

    @property
    def supports_seed(self) -> bool:
        return True

    @property
    def supports_compaction(self) -> bool:
        return True

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
        self,
        artifact_id: str,
        vectors: Iterable[Vector],
        metric: str,
        nd_settings: object | None = None,
    ) -> dict[str, object]:
        vectors_list = list(vectors)
        if not vectors_list:
            return {}
        dim = vectors_list[0].dimension
        if isinstance(nd_settings, NDSettings) and nd_settings.max_index_memory_mb:
            estimated_mb = (len(vectors_list) * dim * 8) / (1024 * 1024)
            if estimated_mb > float(nd_settings.max_index_memory_mb):
                raise BudgetExceededError(
                    message="ANN index memory estimate exceeds limit",
                    dimension="memory",
                )
        data = [vec.values for vec in vectors_list]
        ids = [vec.vector_id for vec in vectors_list]
        build_started = time.time()
        if hnswlib is None:
            self._index = None
        else:
            space = "l2" if metric == "l2" else "cosine"
            index = hnswlib.Index(space=space, dim=dim)
            index.set_seed(0)
            self._apply_nd_settings(
                ExecutionRequest(
                    request_id="ann-build",
                    text=None,
                    vector=vectors_list[0].values,
                    top_k=10,
                    execution_contract=ExecutionContract.NON_DETERMINISTIC,
                    execution_intent=ExecutionIntent.EXPLORATORY_SEARCH,
                    execution_mode=ExecutionMode.BOUNDED,
                    nd_settings=nd_settings
                    if isinstance(nd_settings, NDSettings)
                    else None,
                )
            )
            index.init_index(
                max_elements=len(data),
                ef_construction=100,
                M=getattr(self, "_m", 8),
            )
            index.add_items(data, list(range(len(data))))
            index.set_ef(getattr(self, "_ef_search", 10))
            self._index = index
            if self._index_dir:
                index_file = self._index_dir / f"{artifact_id}.hnsw"
                index.save_index(str(index_file))
        build_time_ms = int((time.time() - build_started) * 1000)
        index_hash = fingerprint(
            {
                "artifact_id": artifact_id,
                "ids": ids,
                "dimension": dim,
                "metric": metric,
            }
        )
        info: dict[str, object] = {
            "index_kind": "hnswlib" if hnswlib else "none",
            "index_params": {
                "M": getattr(self, "_m", 8),
                "ef_search": getattr(self, "_ef_search", 10),
            },
            "build_time_ms": build_time_ms,
            "vector_count": len(ids),
            "index_hash": index_hash,
        }
        self._index_info[artifact_id] = info
        return info

    def index_info(self, artifact_id: str) -> dict[str, object]:
        return dict(self._index_info.get(artifact_id, {}))

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
        index_info = self._index_info.get(artifact.artifact_id, {})
        backend_version = ""
        if hnswlib is not None and hasattr(hnswlib, "__version__"):
            backend_version = str(hnswlib.__version__)
        index_hash = index_info.get("index_hash") if index_info else None
        if index_hash is not None:
            index_hash = str(index_hash)
        return ApproximationReport(
            recall_at_k=recall,
            rank_displacement=displacement,
            distance_error=distance_error,
            algorithm="reference_ann_truncation",
            algorithm_version="v1",
            backend="memory",
            backend_version=backend_version,
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
            candidate_k=getattr(request.nd_settings, "candidate_k", None),
            index_hash=index_hash,
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
                    self._index_info.setdefault(
                        artifact.artifact_id,
                        {
                            "index_kind": "hnswlib",
                            "index_params": {
                                "M": getattr(self, "_m", 8),
                                "ef_search": getattr(self, "_ef_search", 10),
                            },
                            "build_time_ms": None,
                            "vector_count": len(ids),
                            "index_hash": fingerprint(
                                {
                                    "artifact_id": artifact.artifact_id,
                                    "ids": ids,
                                    "dimension": dim,
                                    "metric": artifact.metric,
                                }
                            ),
                        },
                    )
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
        if (
            request.execution_budget is not None
            and request.execution_budget.max_memory_mb is not None
            and len(self._ids) > int(request.execution_budget.max_memory_mb)
        ):
            raise BudgetExceededError(
                message="ANN candidate budget exceeded",
                dimension="candidates",
            )
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
        start = time.time()
        query_k = max(1, int((request.top_k or 1) * self._k_scale))
        labels, distances = self._index.knn_query(
            [query], k=min(query_k, len(self._ids))
        )
        if request.nd_settings is not None:
            elapsed_ms = int((time.time() - start) * 1000)
            self._adaptive_tune(request, elapsed_ms)
            if (
                request.execution_budget is not None
                and request.execution_budget.max_latency_ms is not None
                and elapsed_ms > int(request.execution_budget.max_latency_ms)
            ):
                raise BudgetExceededError(
                    message="ANN latency budget exceeded",
                    dimension="latency",
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

    def warmup(self, artifact_id: str, queries: Iterable[Iterable[float]]) -> None:
        if hnswlib is None or self._index is None:
            return
        warm_k = 1
        for query in queries:
            try:
                if query:
                    self._index.knn_query([tuple(query)], k=warm_k)
            except Exception as exc:
                log_event("nd_warmup_query_failed", error=str(exc))

    def compact(self, artifact_id: str, vectors: Iterable[Vector], metric: str) -> None:
        # Rebuild index to remove tombstones or drift.
        self.build_index(artifact_id, vectors, metric)
        if self._index_dir and hnswlib is not None and self._index is not None:
            index_file = self._index_dir / f"{artifact_id}.hnsw"
            self._index.save_index(str(index_file))

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

    def _adaptive_tune(self, request: ExecutionRequest, elapsed_ms: int) -> None:
        if request.nd_settings is None:
            return
        self._tuning_samples += 1
        if self._tuning_samples > 5:
            return
        budget = request.nd_settings.latency_budget_ms
        if budget is None:
            return
        if elapsed_ms > budget:
            self._ef_search = max(10, int(self._ef_search * 0.8))
            if self._k_scale > 0.5:
                self._k_scale = 0.5
                log_event(
                    "nd_degrade_k",
                    k_scale=self._k_scale,
                    latency_ms=elapsed_ms,
                    budget_ms=budget,
                )
            if self._nd_profile != "fast":
                self._nd_profile = "fast"
                log_event(
                    "nd_degrade_profile",
                    profile=self._nd_profile,
                    latency_ms=elapsed_ms,
                    budget_ms=budget,
                )
        elif (
            request.nd_settings.target_recall
            and request.nd_settings.target_recall > 0.95
        ):
            self._ef_search = min(200, int(self._ef_search * 1.2))
        self._target_recall = request.nd_settings.target_recall
        self._latency_budget_ms = request.nd_settings.latency_budget_ms

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
