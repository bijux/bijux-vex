# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from typing import NoReturn, cast

from fastapi import FastAPI, Header, HTTPException, Response

from bijux_vex.boundaries.exception_bridge import (
    is_refusal,
    record_failure,
    refusal_payload,
    to_http_status,
)
from bijux_vex.boundaries.pydantic_edges.models import (
    BackendCapabilitiesReport,
    CreateRequest,
    ExecutionArtifactRequest,
    ExecutionRequestPayload,
    ExplainRequest,
    IngestRequest,
)
from bijux_vex.core.config import (
    EmbeddingCacheConfig,
    EmbeddingConfig,
    ExecutionConfig,
    VectorStoreConfig,
)
from bijux_vex.core.errors import BijuxError
from bijux_vex.services.execution_engine import VectorExecutionEngine


def build_app() -> FastAPI:
    app = FastAPI(title="bijux-vex execution API", version="v1")

    def _raise_http_error(
        exc: BijuxError, correlation_id: str | None = None
    ) -> NoReturn:
        record_failure(exc)
        detail: object
        if is_refusal(exc):
            detail = {"error": refusal_payload(exc)}
        else:
            detail = {"message": str(exc)}
        headers = {"X-Correlation-Id": correlation_id} if correlation_id else None
        raise HTTPException(
            status_code=to_http_status(exc), detail=detail, headers=headers
        ) from None

    def _config_from_payload(
        *,
        vector_store: str | None = None,
        vector_store_uri: str | None = None,
        vector_store_options: dict[str, str] | None = None,
        embed_provider: str | None = None,
        embed_model: str | None = None,
        cache_embeddings: str | None = None,
    ) -> ExecutionConfig:
        vs_cfg = None
        if vector_store:
            vs_cfg = VectorStoreConfig(
                backend=vector_store,
                uri=vector_store_uri,
                options=vector_store_options,
            )
        embed_cfg = None
        if embed_provider or embed_model or cache_embeddings:
            cache_cfg = (
                EmbeddingCacheConfig(backend=None, uri=cache_embeddings)
                if cache_embeddings
                else None
            )
            embed_cfg = EmbeddingConfig(
                provider=embed_provider,
                model=embed_model,
                cache=cache_cfg,
            )
        return ExecutionConfig(vector_store=vs_cfg, embeddings=embed_cfg)

    @app.get("/capabilities", response_model=BackendCapabilitiesReport)  # type: ignore[untyped-decorator]
    def capabilities(
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> BackendCapabilitiesReport:
        engine = VectorExecutionEngine()
        if correlation_id:
            response.headers["X-Correlation-Id"] = correlation_id
        return cast(
            BackendCapabilitiesReport,
            BackendCapabilitiesReport.model_validate(engine.capabilities()),
        )

    @app.post("/create")  # type: ignore[untyped-decorator]
    def create(
        req: CreateRequest,
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> dict[str, object]:
        try:
            if correlation_id:
                response.headers["X-Correlation-Id"] = correlation_id
            return VectorExecutionEngine().create(req)
        except BijuxError as exc:
            _raise_http_error(exc, correlation_id)
        except Exception as exc:  # pragma: no cover - unexpected
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/ingest")  # type: ignore[untyped-decorator]
    def ingest(
        req: IngestRequest,
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> dict[str, object]:
        try:
            if correlation_id and req.correlation_id is None:
                req = req.model_copy(update={"correlation_id": correlation_id})
            engine = VectorExecutionEngine(
                config=_config_from_payload(
                    vector_store=req.vector_store,
                    vector_store_uri=req.vector_store_uri,
                    vector_store_options=req.vector_store_options,
                    embed_provider=req.embed_provider,
                    embed_model=req.embed_model,
                    cache_embeddings=req.cache_embeddings,
                )
            )
            result = engine.ingest(req)
            response.headers["X-Correlation-Id"] = req.correlation_id or ""
            return result
        except BijuxError as exc:
            _raise_http_error(exc, req.correlation_id or correlation_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/artifact")  # type: ignore[untyped-decorator]
    def artifact(
        req: ExecutionArtifactRequest,
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> dict[str, object]:
        try:
            if correlation_id:
                response.headers["X-Correlation-Id"] = correlation_id
            engine = VectorExecutionEngine(
                config=_config_from_payload(
                    vector_store=req.vector_store,
                    vector_store_uri=req.vector_store_uri,
                    vector_store_options=req.vector_store_options,
                )
            )
            return engine.materialize(req)
        except BijuxError as exc:
            _raise_http_error(exc, correlation_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/execute")  # type: ignore[untyped-decorator]
    def execute(
        req: ExecutionRequestPayload,
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> dict[str, object]:
        try:
            if correlation_id and req.correlation_id is None:
                req = req.model_copy(update={"correlation_id": correlation_id})
            engine = VectorExecutionEngine(
                config=_config_from_payload(
                    vector_store=req.vector_store,
                    vector_store_uri=req.vector_store_uri,
                    vector_store_options=req.vector_store_options,
                )
            )
            result = engine.execute(req)
            response.headers["X-Correlation-Id"] = result.get("correlation_id", "")
            return result
        except BijuxError as exc:
            _raise_http_error(exc, req.correlation_id or correlation_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/explain")  # type: ignore[untyped-decorator]
    def explain(
        req: ExplainRequest,
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> dict[str, object]:
        try:
            result = VectorExecutionEngine().explain(req)
            if correlation_id:
                response.headers["X-Correlation-Id"] = correlation_id
            return result
        except BijuxError as exc:
            _raise_http_error(exc, correlation_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    @app.post("/replay")  # type: ignore[untyped-decorator]
    def replay(
        req: ExecutionRequestPayload,
        response: Response,
        correlation_id: str | None = Header(None, alias="X-Correlation-Id"),
    ) -> dict[str, object]:
        request_text = req.request_text or ""
        try:
            if correlation_id:
                response.headers["X-Correlation-Id"] = correlation_id
            return VectorExecutionEngine().replay(
                request_text, artifact_id=req.artifact_id
            )
        except BijuxError as exc:
            _raise_http_error(exc, correlation_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="internal error") from exc

    return app


app = build_app()

__all__ = ["build_app", "app"]
