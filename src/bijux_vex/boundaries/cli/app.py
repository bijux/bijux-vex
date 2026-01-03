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
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import BijuxError
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode
from bijux_vex.services.execution_engine import VectorExecutionEngine

app = typer.Typer(add_completion=False)


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
    doc: str = typer.Option(..., "--doc"), vector: str = typer.Option(..., "--vector")
) -> None:
    try:
        req = IngestRequest(documents=[doc], vectors=[json.loads(vector)])
        engine = VectorExecutionEngine()
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
) -> None:
    try:
        contract = _parse_contract(execution_contract)
        engine = VectorExecutionEngine()
        result = engine.materialize(
            ExecutionArtifactRequest(execution_contract=contract)
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
        )
        engine = VectorExecutionEngine()
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
        )
        engine = VectorExecutionEngine()
        result = engine.compare(
            payload, artifact_a_id=artifact_a, artifact_b_id=artifact_b
        )
        _echo(result)
    except BijuxError as exc:
        sys.exit(to_cli_exit(exc))
    except Exception:  # pragma: no cover
        sys.exit(1)


if __name__ == "__main__":
    app()
