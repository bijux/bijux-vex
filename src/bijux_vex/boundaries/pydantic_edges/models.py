# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.execution_intent import ExecutionIntent
from bijux_vex.core.execution_mode import ExecutionMode


class StrictModel(BaseModel):  # type: ignore[misc]
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class CreateRequest(StrictModel):
    name: str = Field(min_length=1)


class IngestRequest(StrictModel):
    documents: list[str]
    vectors: list[list[float]] | None = None
    embed_provider: str | None = None
    embed_model: str | None = None
    cache_embeddings: str | None = None
    vector_store: str | None = None
    vector_store_uri: str | None = None
    vector_store_options: dict[str, str] | None = None

    @model_validator(mode="after")  # type: ignore[untyped-decorator]
    def ensure_lengths(self) -> Self:
        if self.vectors:
            if len(self.documents) != len(self.vectors):
                raise ValueError("documents and vectors length mismatch")
        else:
            if not self.embed_model:
                raise ValueError("embed_model required when vectors are omitted")
        return self


class ExecutionBudgetPayload(StrictModel):
    max_latency_ms: int | None = None
    max_memory_mb: int | None = None
    max_error: float | None = None


class RandomnessProfilePayload(StrictModel):
    seed: int | None = None
    sources: list[str] | None = None
    bounded: bool = False


class ExecutionRequestPayload(StrictModel):
    artifact_id: str | None = None
    request_text: str | None = None
    vector: tuple[float, ...] | None = None
    top_k: int = Field(gt=0, default=5)
    execution_contract: ExecutionContract
    execution_intent: ExecutionIntent
    execution_mode: ExecutionMode = ExecutionMode.STRICT
    execution_budget: ExecutionBudgetPayload | None = None
    randomness_profile: RandomnessProfilePayload | None = None
    vector_store: str | None = None
    vector_store_uri: str | None = None
    vector_store_options: dict[str, str] | None = None

    @model_validator(mode="after")  # type: ignore[untyped-decorator]
    def ensure_one_of_request_or_vector(self) -> Self:
        if self.request_text is None and self.vector is None:
            raise ValueError("request_text or vector is required")
        return self

    @model_validator(mode="after")  # type: ignore[untyped-decorator]
    def ensure_randomness_for_nd(self) -> Self:
        if (
            self.execution_contract is ExecutionContract.NON_DETERMINISTIC
            and self.randomness_profile is None
        ):
            raise ValueError(
                "randomness_profile required for non_deterministic execution"
            )
        if (
            self.execution_contract is ExecutionContract.NON_DETERMINISTIC
            and self.execution_budget is None
        ):
            raise ValueError(
                "execution_budget required for non_deterministic execution"
            )
        if not isinstance(self.execution_intent, ExecutionIntent):
            raise ValueError("execution_intent must be a known ExecutionIntent")
        if not isinstance(self.execution_mode, ExecutionMode):
            raise ValueError("execution_mode must be strict|bounded|exploratory")
        if self.execution_contract is ExecutionContract.DETERMINISTIC:
            if self.execution_mode is not ExecutionMode.STRICT:
                raise ValueError("deterministic executions require strict mode")
        else:
            if self.execution_mode is ExecutionMode.STRICT:
                raise ValueError(
                    "non_deterministic executions require bounded or exploratory mode"
                )
        return self


class ExecutionArtifactRequest(StrictModel):
    execution_contract: ExecutionContract
    vector_store: str | None = None
    vector_store_uri: str | None = None
    vector_store_options: dict[str, str] | None = None


class ExplainRequest(StrictModel):
    result_id: str = Field(min_length=1)
    artifact_id: str | None = None


class StorageBackendDescriptor(StrictModel):
    name: str
    status: str
    persistence: str | None = None
    notes: str | None = None


class VectorStoreDescriptor(StrictModel):
    name: str
    available: bool
    supports_exact: bool
    supports_ann: bool
    delete_supported: bool
    filtering_supported: bool
    deterministic_exact: bool
    experimental: bool
    consistency: str | None = None
    version: str | None = None
    notes: str | None = None


class BackendCapabilitiesReport(StrictModel):
    backend: str
    contracts: list[str]
    deterministic_query: bool | None
    supports_ann: bool
    replayable: bool | None
    metrics: list[str]
    max_vector_size: int | None
    isolation_level: str | None
    execution_modes: list[str]
    ann_status: str
    storage_backends: list[StorageBackendDescriptor]
    vector_stores: list[VectorStoreDescriptor]
