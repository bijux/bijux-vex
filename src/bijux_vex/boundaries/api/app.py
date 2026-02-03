# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from typing import cast

from fastapi import FastAPI, HTTPException

from bijux_vex.boundaries.exception_bridge import to_http_status
from bijux_vex.boundaries.pydantic_edges.models import (
    BackendCapabilitiesReport,
    CreateRequest,
    ExecutionArtifactRequest,
    ExecutionRequestPayload,
    ExplainRequest,
    IngestRequest,
)
from bijux_vex.core.errors import BijuxError
from bijux_vex.services.execution_engine import VectorExecutionEngine


def build_app() -> FastAPI:
    app = FastAPI(title="bijux-vex execution API", version="v1")

    @app.get("/capabilities", response_model=BackendCapabilitiesReport)  # type: ignore[untyped-decorator]
    def capabilities() -> BackendCapabilitiesReport:
        engine = VectorExecutionEngine()
        return cast(
            BackendCapabilitiesReport,
            BackendCapabilitiesReport.model_validate(engine.capabilities()),
        )

    @app.post("/create")  # type: ignore[untyped-decorator]
    def create(req: CreateRequest) -> dict[str, object]:
        try:
            return VectorExecutionEngine().create(req)
        except BijuxError as exc:
            raise HTTPException(
                status_code=to_http_status(exc), detail=str(exc)
            ) from None
        except Exception as exc:  # pragma: no cover - unexpected
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/ingest")  # type: ignore[untyped-decorator]
    def ingest(req: IngestRequest) -> dict[str, object]:
        try:
            return VectorExecutionEngine().ingest(req)
        except BijuxError as exc:
            raise HTTPException(
                status_code=to_http_status(exc), detail=str(exc)
            ) from None
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/artifact")  # type: ignore[untyped-decorator]
    def artifact(req: ExecutionArtifactRequest) -> dict[str, object]:
        try:
            return VectorExecutionEngine().materialize(req)
        except BijuxError as exc:
            raise HTTPException(
                status_code=to_http_status(exc), detail=str(exc)
            ) from None
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/execute")  # type: ignore[untyped-decorator]
    def execute(req: ExecutionRequestPayload) -> dict[str, object]:
        try:
            return VectorExecutionEngine().execute(req)
        except BijuxError as exc:
            raise HTTPException(
                status_code=to_http_status(exc), detail=str(exc)
            ) from None
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/explain")  # type: ignore[untyped-decorator]
    def explain(req: ExplainRequest) -> dict[str, object]:
        try:
            return VectorExecutionEngine().explain(req)
        except BijuxError as exc:
            raise HTTPException(
                status_code=to_http_status(exc), detail=str(exc)
            ) from None
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/replay")  # type: ignore[untyped-decorator]
    def replay(req: ExecutionRequestPayload) -> dict[str, object]:
        request_text = req.request_text or ""
        try:
            return VectorExecutionEngine().replay(
                request_text, artifact_id=req.artifact_id
            )
        except BijuxError as exc:
            raise HTTPException(
                status_code=to_http_status(exc), detail=str(exc)
            ) from None
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    return app


app = build_app()

__all__ = ["build_app", "app"]
