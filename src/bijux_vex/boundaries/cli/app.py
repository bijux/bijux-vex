# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import no_type_check

import typer

from bijux_vex.bench.dataset import (
    DEFAULT_DIMENSION,
    DEFAULT_QUERY_COUNT,
    DEFAULT_SEED,
    dataset_folder,
    generate_dataset,
    load_dataset,
    save_dataset,
)
from bijux_vex.bench.runner import format_table, run_benchmark
from bijux_vex.boundaries.exception_bridge import (
    is_refusal,
    record_failure,
    refusal_payload,
    to_cli_exit,
)
from bijux_vex.boundaries.pydantic_edges.models import (
    ExecutionArtifactRequest,
    ExecutionBudgetPayload,
    ExecutionRequestPayload,
    ExplainRequest,
    IngestRequest,
    RandomnessProfilePayload,
)
from bijux_vex.core.config import (
    EmbeddingCacheConfig,
    EmbeddingConfig,
    ExecutionConfig,
    VectorStoreConfig,
)
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import BijuxError, ValidationError
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.infra.adapters.vectorstore_registry import VECTOR_STORES
from bijux_vex.infra.metrics import METRICS
from bijux_vex.services.execution_engine import VectorExecutionEngine

app = typer.Typer(add_completion=False)
vdb_app = typer.Typer(add_completion=False, help="Vector DB utilities")
app.add_typer(vdb_app, name="vdb")
config_app = typer.Typer(add_completion=False, help="Configuration utilities")
app.add_typer(config_app, name="config")


@dataclass(frozen=True)
class OutputOptions:
    fmt: str | None = None
    output: Path | None = None
    config_path: Path | None = None


@app.callback()
@no_type_check
def _main_callback(
    ctx: typer.Context,
    fmt: str | None = typer.Option(
        None, "--format", help="Output format: json|table (default: json)"
    ),
    output: Path | None = typer.Option(  # noqa: B008
        None, "--output", help="Write output to a file"
    ),
    config: Path | None = typer.Option(  # noqa: B008
        None, "--config", help="Load configuration from a TOML/YAML file"
    ),
) -> None:
    ctx.obj = OutputOptions(fmt=fmt, output=output, config_path=config)


def _render_table(data: object) -> str:
    if isinstance(data, dict):
        lines = ["key | value", "---- | -----"]
        for key, value in data.items():
            lines.append(f"{key} | {value}")
        return "\n".join(lines)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        keys = list(data[0].keys())
        header = " | ".join(keys)
        divider = " | ".join(["---"] * len(keys))
        lines = [header, divider]
        for row in data:
            lines.append(" | ".join(str(row.get(k, "")) for k in keys))
        return "\n".join(lines)
    return str(data)


def _emit(
    ctx: typer.Context | None,
    data: object,
    *,
    table: str | None = None,
) -> None:
    options: OutputOptions | None = getattr(ctx, "obj", None) if ctx else None
    fmt = options.fmt if options else None
    output = options.output if options else None
    if fmt == "table":
        payload = table or _render_table(data)
        typer.echo(payload)
        if output:
            output.write_text(payload, encoding="utf-8")
        return
    if fmt is None and table is not None:
        typer.echo(table)
    payload = json.dumps(data, default=str)
    typer.echo(payload)
    if output:
        output.write_text(payload, encoding="utf-8")


def _config_to_dict(config: ExecutionConfig | None) -> dict[str, object]:
    if config is None:
        return {}
    return asdict(config)


def _redact_config(config: ExecutionConfig | None) -> dict[str, object]:
    payload = _config_to_dict(config)
    vs = payload.get("vector_store")
    if isinstance(vs, dict) and vs.get("uri"):
        resolved = VECTOR_STORES.resolve(
            vs.get("backend") or "memory", uri=str(vs.get("uri"))
        )
        vs["uri"] = resolved.uri_redacted
    return payload


def _parse_contract(raw: str) -> ExecutionContract:
    try:
        return ExecutionContract(raw)
    except Exception:
        typer.echo("execution-contract must be one of deterministic|non_deterministic")
        sys.exit(1)


def _parse_mode(raw: str) -> ExecutionMode:
    try:
        return ExecutionMode(raw)
    except Exception:
        typer.echo("execution-mode must be one of strict|bounded|exploratory")
        sys.exit(1)


ALLOWED_INTENTS = {intent.value for intent in ExecutionIntent}


def _parse_intent(raw: str) -> ExecutionIntent:
    if raw not in ALLOWED_INTENTS:
        allowed = "|".join(sorted(ALLOWED_INTENTS))
        typer.echo(f"execution-intent must be one of {allowed}")
        sys.exit(1)
    return ExecutionIntent(raw)


def _load_config(config_path: Path | None) -> ExecutionConfig | None:
    if not config_path:
        return None
    suffix = config_path.suffix.lower()
    if suffix in {".toml", ".tml"}:
        import tomllib

        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except Exception as exc:  # pragma: no cover
            raise ValueError(
                "YAML config requires PyYAML. Install with extras or use TOML."
            ) from exc
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        raise ValueError("config file must be .toml or .yaml/.yml")
    vector_store_cfg = payload.get("vector_store") or {}
    embed_cfg = payload.get("embeddings") or {}
    cache_cfg = embed_cfg.get("cache") or {}
    vs_config = None
    if vector_store_cfg.get("backend"):
        vs_config = VectorStoreConfig(
            backend=vector_store_cfg.get("backend"),
            uri=vector_store_cfg.get("uri"),
        )
    embed_config = None
    if embed_cfg.get("provider") or embed_cfg.get("model") or cache_cfg.get("uri"):
        embed_config = EmbeddingConfig(
            provider=embed_cfg.get("provider"),
            model=embed_cfg.get("model"),
            cache=(
                EmbeddingCacheConfig(
                    backend=cache_cfg.get("backend"),
                    uri=cache_cfg.get("uri"),
                )
                if cache_cfg
                else None
            ),
        )
    return ExecutionConfig(vector_store=vs_config, embeddings=embed_config)


def _build_config(
    *,
    vector_store: str | None = None,
    vector_store_uri: str | None = None,
    embed_provider: str | None = None,
    embed_model: str | None = None,
    cache_embeddings: str | None = None,
    base_config: ExecutionConfig | None = None,
) -> ExecutionConfig:
    vs_config = base_config.vector_store if base_config else None
    if vector_store:
        vs_config = VectorStoreConfig(backend=vector_store, uri=vector_store_uri)
    embed_config = base_config.embeddings if base_config else None
    if embed_model or embed_provider or cache_embeddings:
        cache_cfg = (
            EmbeddingCacheConfig(backend=None, uri=cache_embeddings)
            if cache_embeddings
            else None
        )
        embed_config = EmbeddingConfig(
            provider=embed_provider,
            model=embed_model,
            cache=cache_cfg,
        )
    return ExecutionConfig(vector_store=vs_config, embeddings=embed_config)


@app.command()
@no_type_check
def list_artifacts(ctx: typer.Context) -> None:
    _emit(ctx, VectorExecutionEngine().list_artifacts())


@app.command()
@no_type_check
def capabilities(ctx: typer.Context) -> None:
    _emit(ctx, VectorExecutionEngine().capabilities())


@app.command()
@no_type_check
def ingest(
    ctx: typer.Context,
    doc: str = typer.Option(..., "--doc"),
    vector: str | None = typer.Option(None, "--vector"),
    embed_model: str | None = typer.Option(None, "--embed-model"),
    embed_provider: str | None = typer.Option(None, "--embed-provider"),
    cache_embeddings: str | None = typer.Option(None, "--cache-embeddings"),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    try:
        base_config = _load_config(ctx.obj.config_path) if ctx.obj else None
        req = IngestRequest(
            documents=[doc],
            vectors=[json.loads(vector)] if vector else None,
            embed_model=embed_model,
            embed_provider=embed_provider,
            cache_embeddings=cache_embeddings,
            correlation_id=correlation_id,
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
        )
        config = _build_config(
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
            embed_model=embed_model,
            embed_provider=embed_provider,
            cache_embeddings=cache_embeddings,
            base_config=base_config,
        )
        if dry_run:
            output = {
                "resolved_config": _config_to_dict(config),
                "determinism": "deterministic"
                if config.vector_store is None
                else "deterministic_with_vector_store",
                "provenance_fields": [
                    "vector_store_backend",
                    "vector_store_uri_redacted",
                    "vector_store_index_params",
                ]
                if config.vector_store
                else [],
            }
            _emit(ctx, output)
            return
        engine = VectorExecutionEngine(config=config)
        result = engine.ingest(req)
        _emit(ctx, result)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def materialize(
    ctx: typer.Context,
    execution_contract: str = typer.Option(
        ...,
        "--execution-contract",
        help="Execution contract (deterministic warns: non_deterministic loses replay guarantees)",
    ),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
) -> None:
    try:
        contract = _parse_contract(execution_contract)
        base_config = _load_config(ctx.obj.config_path) if ctx.obj else None
        engine = VectorExecutionEngine(
            config=_build_config(
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
                base_config=base_config,
            )
        )
        result = engine.materialize(
            ExecutionArtifactRequest(
                execution_contract=contract,
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
            )
        )
        _emit(ctx, result)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def execute(
    ctx: typer.Context,
    request_text: str | None = None,
    vector: str | None = None,
    top_k: int = 5,
    artifact_id: str = typer.Option(
        "art-1", "--artifact-id", help="Target execution artifact id"
    ),
    execution_contract: str = typer.Option(
        ...,
        "--execution-contract",
        help="Execution contract (deterministic preferred; non_deterministic is approximate)",
    ),
    execution_intent: str = typer.Option(
        ...,
        "--execution-intent",
        help="Execution intent (explains why determinism or loss is acceptable)",
    ),
    execution_mode: str = typer.Option(
        "strict",
        "--execution-mode",
        help="Execution mode: strict|bounded|exploratory",
    ),
    randomness_seed: int | None = typer.Option(None, "--randomness-seed"),
    randomness_sources: str | None = typer.Option(
        None,
        "--randomness-sources",
        help="Comma-separated randomness sources (required for non_deterministic)",
    ),
    randomness_bounded: bool = typer.Option(
        False, "--randomness-bounded", help="Whether randomness is bounded"
    ),
    max_latency_ms: int | None = typer.Option(None, "--max-latency-ms"),
    max_memory_mb: int | None = typer.Option(None, "--max-memory-mb"),
    max_error: float | None = typer.Option(None, "--max-error"),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    explain: bool = typer.Option(False, "--explain"),
) -> None:
    try:
        vector_parsed = json.loads(vector) if vector else None
        contract = _parse_contract(execution_contract)
        intent = _parse_intent(execution_intent)
        mode = _parse_mode(execution_mode)
        sources = (
            [s.strip() for s in randomness_sources.split(",")]
            if randomness_sources
            else None
        )
        req = ExecutionRequestPayload(
            request_text=request_text,
            vector=tuple(vector_parsed) if vector_parsed else None,
            top_k=top_k,
            artifact_id=artifact_id,
            execution_contract=contract,
            execution_intent=intent,
            execution_mode=mode,
            randomness_profile=RandomnessProfilePayload.model_validate(
                {
                    "seed": randomness_seed,
                    "sources": sources,
                    "bounded": randomness_bounded,
                }
            )
            if contract is ExecutionContract.NON_DETERMINISTIC
            else None,
            execution_budget=ExecutionBudgetPayload(
                max_latency_ms=max_latency_ms,
                max_memory_mb=max_memory_mb,
                max_error=max_error,
            ),
            correlation_id=correlation_id,
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
        )
        base_config = _load_config(ctx.obj.config_path) if ctx.obj else None
        config = _build_config(
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
            base_config=base_config,
        )
        if dry_run:
            vs_descriptor = None
            if config.vector_store:
                store_name = config.vector_store.backend
                vs_descriptor = next(
                    (d for d in VECTOR_STORES.descriptors() if d.name == store_name),
                    None,
                )
            output = {
                "resolved_config": _config_to_dict(config),
                "determinism": contract.value,
                "vector_store": vs_descriptor.name if vs_descriptor else None,
                "provenance_fields": [
                    "execution_id",
                    "result_id",
                    "vector_store_backend",
                    "vector_store_uri_redacted",
                    "vector_store_index_params",
                ],
            }
            _emit(ctx, output)
            return
        engine = VectorExecutionEngine(config=config)
        result = engine.execute(req)
        if explain:
            explain_result = engine.explain(
                ExplainRequest(result_id=result["result_id"])
            )
            _emit(
                ctx,
                {"result": result, "explain": explain_result},
            )
            return
        _emit(ctx, result)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def explain(
    ctx: typer.Context, result_id: str = typer.Option(..., "--result-id")
) -> None:
    try:
        req = ExplainRequest(result_id=result_id)
        engine = VectorExecutionEngine()
        result = engine.explain(req)
        _emit(ctx, result)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def replay(
    ctx: typer.Context, request_text: str = typer.Option(..., "--request-text")
) -> None:
    try:
        engine = VectorExecutionEngine()
        result = engine.replay(request_text)
        _emit(ctx, result)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def compare(
    ctx: typer.Context,
    vector: str = typer.Option(..., "--vector"),
    top_k: int = 5,
    execution_intent: str = typer.Option(
        ...,
        "--execution-intent",
        help="Execution intent for the comparison request",
    ),
    execution_contract: str = typer.Option(
        "deterministic",
        "--execution-contract",
        help="Contract placeholder for payload validation; artifacts govern actual contract",
    ),
    artifact_a: str = typer.Option("art-1", "--artifact-a"),
    artifact_b: str = typer.Option("art-1", "--artifact-b"),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
) -> None:
    try:
        intent = _parse_intent(execution_intent)
        contract = _parse_contract(execution_contract)
        payload = ExecutionRequestPayload(
            request_text=None,
            vector=tuple(json.loads(vector)),
            top_k=top_k,
            execution_contract=contract,
            execution_intent=intent,
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
        )
        base_config = _load_config(ctx.obj.config_path) if ctx.obj else None
        engine = VectorExecutionEngine(
            config=_build_config(
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
                base_config=base_config,
            )
        )
        result = engine.compare(
            payload, artifact_a_id=artifact_a, artifact_b_id=artifact_b
        )
        _emit(ctx, result)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@vdb_app.command("status")
@no_type_check
def vdb_status(
    ctx: typer.Context,
    vector_store: str = typer.Option(..., "--vector-store"),
    uri: str | None = typer.Option(None, "--uri"),
) -> None:
    try:
        engine = VectorExecutionEngine(
            config=_build_config(vector_store=vector_store, vector_store_uri=uri)
        )
        adapter = engine.vector_store_resolution.adapter
        status = {
            "backend": engine.vector_store_resolution.descriptor.name,
            "reachable": True,
            "version": engine.vector_store_resolution.descriptor.version,
            "uri_redacted": engine.vector_store_resolution.uri_redacted,
        }
        if hasattr(adapter, "status"):
            status.update(adapter.status())
        _emit(ctx, status)
    except BijuxError as exc:
        record_failure(exc)
        payload = {"backend": vector_store, "reachable": False}
        if is_refusal(exc):
            payload["error"] = refusal_payload(exc)
        else:
            payload["error"] = {"message": str(exc)}
        _emit(ctx, payload)
    except Exception:  # pragma: no cover
        sys.exit(1)


@vdb_app.command("rebuild")
@no_type_check
def vdb_rebuild(
    ctx: typer.Context,
    vector_store: str = typer.Option(..., "--vector-store"),
    uri: str | None = typer.Option(None, "--uri"),
    mode: str = typer.Option("exact", "--mode", help="exact|ann"),
) -> None:
    try:
        engine = VectorExecutionEngine(
            config=_build_config(vector_store=vector_store, vector_store_uri=uri)
        )
        adapter = engine.vector_store_resolution.adapter
        if not hasattr(adapter, "rebuild"):
            raise ValidationError(
                message="Selected vector store does not support rebuild"
            )
        index_type = "exact" if mode == "exact" else "ann"
        status = adapter.rebuild(index_type=index_type)
        _emit(ctx, status)
    except BijuxError as exc:
        record_failure(exc)
        payload = {"backend": vector_store, "reachable": False}
        if is_refusal(exc):
            payload["error"] = refusal_payload(exc)
        else:
            payload["error"] = {"message": str(exc)}
        _emit(ctx, payload)
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def bench(
    ctx: typer.Context,
    size: int = typer.Option(1000, "--size", help="Dataset size (1k/10k/100k)"),
    mode: str = typer.Option("exact", "--mode", help="exact|ann"),
    store: str = typer.Option("memory", "--store", help="memory|vdb"),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
    repeats: int = typer.Option(3, "--repeats"),
    warmup: int = typer.Option(1, "--warmup"),
    seed: int = typer.Option(DEFAULT_SEED, "--seed"),
    dimension: int = typer.Option(DEFAULT_DIMENSION, "--dimension"),
    query_count: int = typer.Option(DEFAULT_QUERY_COUNT, "--query-count"),
    dataset_dir: Path = typer.Option(  # noqa: B008
        Path("benchmarks/artifacts"), "--dataset-dir"
    ),
    baseline: Path | None = typer.Option(None, "--baseline"),  # noqa: B008
    fail_on_regression: bool = typer.Option(False, "--fail-on-regression"),
    regress_threshold: float = typer.Option(0.2, "--regress-threshold"),
) -> None:
    try:
        if store not in {"memory", "vdb"}:
            typer.echo("store must be memory|vdb")
            sys.exit(1)
        backend = None
        if store == "vdb":
            backend = vector_store or "faiss"
        base = dataset_dir
        folder = dataset_folder(base, size, dimension, seed)
        if not folder.exists():
            dataset = generate_dataset(
                size=size, dimension=dimension, query_count=query_count, seed=seed
            )
            save_dataset(dataset, folder)
        dataset = load_dataset(folder)
        result = run_benchmark(
            documents=dataset.documents,
            vectors=dataset.vectors,
            queries=dataset.queries,
            store_backend=backend,
            store_uri=vector_store_uri,
            mode=mode,
            top_k=5,
            repeats=repeats,
            warmup=warmup,
        )
        table = format_table(result["summary"])
        if baseline:
            baseline_payload = json.loads(baseline.read_text(encoding="utf-8"))
            base_summary = baseline_payload.get("summary", {})
            if base_summary:
                slowdown = (
                    result["summary"]["mean_ms"] / base_summary.get("mean_ms", 1.0)
                ) - 1.0
                result["regression"] = {
                    "slowdown_pct": slowdown * 100.0,
                    "threshold_pct": regress_threshold * 100.0,
                    "regressed": slowdown > regress_threshold,
                }
                if slowdown > regress_threshold and fail_on_regression:
                    _emit(ctx, result, table=table)
                    sys.exit(2)
        _emit(ctx, result, table=table)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@config_app.command("show")
@no_type_check
def config_show(ctx: typer.Context) -> None:
    try:
        config = _load_config(ctx.obj.config_path) if ctx.obj else None
        _emit(ctx, _redact_config(config))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command("metrics")
@no_type_check
def metrics_snapshot(ctx: typer.Context) -> None:
    try:
        snapshot = METRICS.snapshot()
        _emit(
            ctx,
            {"counters": snapshot.counters, "timers_ms": snapshot.timers_ms},
        )
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command("debug-bundle")
@no_type_check
def debug_bundle(
    ctx: typer.Context,
    include_provenance: bool = typer.Option(False, "--include-provenance"),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
) -> None:
    try:
        base_config = _load_config(ctx.obj.config_path) if ctx.obj else None
        config = _build_config(
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
            base_config=base_config,
        )
        engine = VectorExecutionEngine(config=config)
        status = {
            "backend": engine.vector_store_resolution.descriptor.name,
            "reachable": True,
            "version": engine.vector_store_resolution.descriptor.version,
            "uri_redacted": engine.vector_store_resolution.uri_redacted,
        }
        adapter = engine.vector_store_resolution.adapter
        if hasattr(adapter, "status"):
            status.update(adapter.status())
        bundle: dict[str, object] = {
            "config": _redact_config(config),
            "capabilities": engine.capabilities(),
            "vector_store_status": status,
            "metrics": METRICS.snapshot().__dict__,
        }
        if include_provenance:
            artifacts = tuple(engine.stores.ledger.list_artifacts())
            latest_exec: dict[str, str] = {}
            for artifact in artifacts:
                stored = engine.stores.ledger.latest_execution_result(
                    artifact.artifact_id
                )
                if stored is not None:
                    latest_exec[artifact.artifact_id] = stored.execution_id
            bundle["provenance"] = {
                "artifacts": [a.artifact_id for a in artifacts],
                "latest_execution_ids": latest_exec,
            }
        _emit(ctx, bundle)
    except BijuxError as exc:
        record_failure(exc)
        if is_refusal(exc):
            _emit(ctx, {"error": refusal_payload(exc)})
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


if __name__ == "__main__":
    app()
