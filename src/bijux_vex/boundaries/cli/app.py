# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

import json
import sys
from typing import no_type_check

import typer

from bijux_vex.boundaries.exception_bridge import to_cli_exit
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
from bijux_vex.core.errors import BijuxError
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.services.execution_engine import VectorExecutionEngine

app = typer.Typer(add_completion=False)
vdb_app = typer.Typer(add_completion=False, help="Vector DB utilities")
app.add_typer(vdb_app, name="vdb")


def _echo(data: object) -> None:
    typer.echo(json.dumps(data, default=str))


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


def _build_config(
    *,
    vector_store: str | None = None,
    vector_store_uri: str | None = None,
    embed_provider: str | None = None,
    embed_model: str | None = None,
    cache_embeddings: str | None = None,
) -> ExecutionConfig:
    vs_config = None
    if vector_store:
        vs_config = VectorStoreConfig(backend=vector_store, uri=vector_store_uri)
    embed_config = None
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
def list_artifacts() -> None:
    _echo(VectorExecutionEngine().list_artifacts())


@app.command()
@no_type_check
def capabilities() -> None:
    _echo(VectorExecutionEngine().capabilities())


@app.command()
@no_type_check
def ingest(
    doc: str = typer.Option(..., "--doc"),
    vector: str | None = typer.Option(None, "--vector"),
    embed_model: str | None = typer.Option(None, "--embed-model"),
    embed_provider: str | None = typer.Option(None, "--embed-provider"),
    cache_embeddings: str | None = typer.Option(None, "--cache-embeddings"),
    vector_store: str | None = typer.Option(None, "--vector-store"),
    vector_store_uri: str | None = typer.Option(None, "--vector-store-uri"),
) -> None:
    try:
        req = IngestRequest(
            documents=[doc],
            vectors=[json.loads(vector)] if vector else None,
            embed_model=embed_model,
            embed_provider=embed_provider,
            cache_embeddings=cache_embeddings,
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
        )
        engine = VectorExecutionEngine(
            config=_build_config(
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
                embed_model=embed_model,
                embed_provider=embed_provider,
                cache_embeddings=cache_embeddings,
            )
        )
        result = engine.ingest(req)
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def materialize(
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
        engine = VectorExecutionEngine(
            config=_build_config(
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
            )
        )
        result = engine.materialize(
            ExecutionArtifactRequest(
                execution_contract=contract,
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
            )
        )
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def execute(
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
            vector_store=vector_store,
            vector_store_uri=vector_store_uri,
        )
        engine = VectorExecutionEngine(
            config=_build_config(
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
            )
        )
        result = engine.execute(req)
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def explain(result_id: str = typer.Option(..., "--result-id")) -> None:
    try:
        req = ExplainRequest(result_id=result_id)
        engine = VectorExecutionEngine()
        result = engine.explain(req)
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def replay(request_text: str = typer.Option(..., "--request-text")) -> None:
    try:
        engine = VectorExecutionEngine()
        result = engine.replay(request_text)
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@app.command()
@no_type_check
def compare(
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
        engine = VectorExecutionEngine(
            config=_build_config(
                vector_store=vector_store,
                vector_store_uri=vector_store_uri,
            )
        )
        result = engine.compare(
            payload, artifact_a_id=artifact_a, artifact_b_id=artifact_b
        )
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


@vdb_app.command("status")
@no_type_check
def vdb_status(
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
        _echo(status)
    except BijuxError as exc:
        _echo({"backend": vector_store, "reachable": False, "error": str(exc)})
    except Exception:  # pragma: no cover
        sys.exit(1)


if __name__ == "__main__":
    app()
