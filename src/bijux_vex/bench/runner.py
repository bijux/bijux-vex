# SPDX-License-Identifier: MIT
# Copyright © 2026 Bijan Mousavi
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import platform
import statistics
import time
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

from bijux_vex.boundaries.pydantic_edges.models import (
    ExecutionArtifactRequest,
    ExecutionBudgetPayload,
    ExecutionRequestPayload,
    IngestRequest,
    RandomnessProfilePayload,
)
from bijux_vex.core.config import ExecutionConfig, VectorStoreConfig
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.services.execution_engine import VectorExecutionEngine


@dataclass(frozen=True)
class BenchmarkRun:
    timings_ms: list[float]
    throughput_qps: float
    warmup_ms: float

    @property
    def p50(self) -> float:
        return statistics.median(self.timings_ms)

    @property
    def p95(self) -> float:
        return statistics.quantiles(self.timings_ms, n=100)[94]

    @property
    def p99(self) -> float:
        return statistics.quantiles(self.timings_ms, n=100)[98]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.timings_ms)


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _build_engine(
    store_backend: str | None, store_uri: str | None
) -> VectorExecutionEngine:
    config = None
    if store_backend:
        config = ExecutionConfig(
            vector_store=VectorStoreConfig(backend=store_backend, uri=store_uri)
        )
    return VectorExecutionEngine(config=config)


def _ingest(
    engine: VectorExecutionEngine, documents: list[str], vectors: np.ndarray
) -> None:
    req = IngestRequest(
        documents=documents,
        vectors=[vec.tolist() for vec in vectors],
    )
    engine.ingest(req)


def _materialize(engine: VectorExecutionEngine, contract: ExecutionContract) -> str:
    result = engine.materialize(ExecutionArtifactRequest(execution_contract=contract))
    return str(result["artifact_id"])


def _execute_queries(
    engine: VectorExecutionEngine,
    artifact_id: str,
    contract: ExecutionContract,
    mode: ExecutionMode,
    intent: ExecutionIntent,
    queries: Iterable[np.ndarray],
    top_k: int,
    budget: ExecutionBudgetPayload | None,
    randomness: RandomnessProfilePayload | None,
    repeats: int,
) -> BenchmarkRun:
    timings_ms: list[float] = []
    start_warmup = _now_ms()
    for _ in range(repeats):
        for query in queries:
            req = ExecutionRequestPayload(
                request_text=None,
                vector=tuple(float(x) for x in query.tolist()),
                top_k=top_k,
                artifact_id=artifact_id,
                execution_contract=contract,
                execution_intent=intent,
                execution_mode=mode,
                execution_budget=budget,
                randomness_profile=randomness,
            )
            engine.execute(req)
    warmup_ms = _now_ms() - start_warmup

    for _ in range(repeats):
        for query in queries:
            req = ExecutionRequestPayload(
                request_text=None,
                vector=tuple(float(x) for x in query.tolist()),
                top_k=top_k,
                artifact_id=artifact_id,
                execution_contract=contract,
                execution_intent=intent,
                execution_mode=mode,
                execution_budget=budget,
                randomness_profile=randomness,
            )
            start = _now_ms()
            engine.execute(req)
            timings_ms.append(_now_ms() - start)

    total_time = sum(timings_ms) / 1000.0
    throughput = (len(timings_ms) / total_time) if total_time > 0 else 0.0
    return BenchmarkRun(
        timings_ms=timings_ms,
        throughput_qps=throughput,
        warmup_ms=warmup_ms,
    )


def run_benchmark(
    *,
    documents: list[str],
    vectors: np.ndarray,
    queries: np.ndarray,
    store_backend: str | None,
    store_uri: str | None,
    mode: str,
    top_k: int,
    repeats: int,
    warmup: int,
) -> dict[str, Any]:
    if mode not in {"exact", "ann"}:
        raise ValueError("mode must be exact or ann")

    contract = (
        ExecutionContract.DETERMINISTIC
        if mode == "exact"
        else ExecutionContract.NON_DETERMINISTIC
    )
    intent = (
        ExecutionIntent.EXACT_VALIDATION
        if mode == "exact"
        else ExecutionIntent.EXPLORATORY_SEARCH
    )
    execution_mode = ExecutionMode.STRICT if mode == "exact" else ExecutionMode.BOUNDED
    budget = (
        None
        if mode == "exact"
        else ExecutionBudgetPayload(max_latency_ms=10, max_memory_mb=64, max_error=0.5)
    )
    randomness = (
        None
        if mode == "exact"
        else RandomnessProfilePayload(
            seed=0, sources=["reference_ann_hnsw"], bounded=True
        )
    )

    engine = _build_engine(store_backend, store_uri)
    _ingest(engine, documents, vectors)
    artifact_id = _materialize(engine, contract)
    exact_artifact_id = None
    if mode == "ann":
        exact_artifact_id = _materialize(engine, ExecutionContract.DETERMINISTIC)

    warmup_run = _execute_queries(
        engine,
        artifact_id,
        contract,
        execution_mode,
        intent,
        queries,
        top_k,
        budget,
        randomness,
        warmup,
    )
    run = _execute_queries(
        engine,
        artifact_id,
        contract,
        execution_mode,
        intent,
        queries,
        top_k,
        budget,
        randomness,
        repeats,
    )

    result: dict[str, Any] = {
        "dataset": {
            "size": len(documents),
            "dimension": int(vectors.shape[1]),
            "query_count": int(queries.shape[0]),
        },
        "mode": mode,
        "store_backend": store_backend or "memory",
        "timings_ms": run.timings_ms,
        "summary": {
            "mean_ms": run.mean,
            "p50_ms": run.p50,
            "p95_ms": run.p95,
            "p99_ms": run.p99,
            "throughput_qps": run.throughput_qps,
            "warmup_ms": warmup_run.warmup_ms,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
        },
    }
    if mode == "ann" and exact_artifact_id:
        overlaps = []
        instabilities = []
        recall_deltas = []
        for query in queries:
            payload = ExecutionRequestPayload(
                request_text=None,
                vector=tuple(float(x) for x in query.tolist()),
                top_k=top_k,
                execution_contract=ExecutionContract.NON_DETERMINISTIC,
                execution_intent=ExecutionIntent.EXPLORATORY_SEARCH,
                execution_mode=ExecutionMode.BOUNDED,
                execution_budget=budget,
                randomness_profile=randomness,
            )
            diff = engine.compare(
                payload,
                artifact_a_id=artifact_id,
                artifact_b_id=exact_artifact_id,
            )
            overlaps.append(float(cast(float, diff["overlap_ratio"])))
            instabilities.append(float(cast(float, diff["rank_instability"])))
            recall_deltas.append(float(cast(float, diff["recall_delta"])))
        mean_overlap = statistics.fmean(overlaps) if overlaps else 0.0
        mean_instability = statistics.fmean(instabilities) if instabilities else 0.0
        mean_recall_delta = statistics.fmean(recall_deltas) if recall_deltas else 0.0
        result["quality"] = {
            "overlap_at_k": mean_overlap,
            "rank_instability": mean_instability,
            "kendall_tau_estimate": 1.0 - mean_instability,
            "recall_delta": mean_recall_delta,
            "latency_distribution_ms": {
                "p50": run.p50,
                "p95": run.p95,
                "p99": run.p99,
            },
            "cost_estimate_ms": run.mean,
        }
    return result


def format_table(summary: dict[str, Any]) -> str:
    rows = [
        ("mean_ms", summary["mean_ms"]),
        ("p50_ms", summary["p50_ms"]),
        ("p95_ms", summary["p95_ms"]),
        ("p99_ms", summary["p99_ms"]),
        ("throughput_qps", summary["throughput_qps"]),
        ("warmup_ms", summary["warmup_ms"]),
    ]
    lines = ["metric | value", "------ | -----"]
    for key, value in rows:
        lines.append(f"{key} | {value:.4f}")
    return "\n".join(lines)
