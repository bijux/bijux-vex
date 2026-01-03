# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from bijux_vex.core.contracts.ann_metadata import derive_metadata
from bijux_vex.core.contracts.determinism import DeterminismReport
from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import InvariantError
from bijux_vex.core.execution_result import (
    ApproximationReport,
    ExecutionCost,
    ExecutionResult,
    ExecutionStatus,
)
from bijux_vex.core.runtime.execution_session import ExecutionSession
from bijux_vex.core.runtime.vector_execution import execution_signature
from bijux_vex.core.types import Result
from bijux_vex.domain.execution_requests.budget import apply_budget_outcomes


def randomness_audit(
    session: ExecutionSession,
) -> tuple[
    tuple[str, ...], tuple[tuple[str, int | float], ...], tuple[tuple[str, float], ...]
]:
    randomness_sources: tuple[str, ...] = ()
    randomness_budget: tuple[tuple[str, int | float], ...] = ()
    randomness_envelopes: tuple[tuple[str, float], ...] = ()
    if session.randomness:
        randomness_sources = tuple(session.randomness.sources)
        randomness_budget = tuple(sorted((session.randomness.budget or {}).items()))
        randomness_envelopes = tuple(session.randomness.envelopes)
    return randomness_sources, randomness_budget, randomness_envelopes


def guard_nd_randomness(
    session: ExecutionSession,
    randomness_sources: tuple[str, ...],
    randomness_budget: tuple[tuple[str, int | float], ...],
    randomness_envelopes: tuple[tuple[str, float], ...],
    approximation: ApproximationReport | None,
) -> None:
    if session.request.execution_contract is not ExecutionContract.NON_DETERMINISTIC:
        return
    if (
        not randomness_sources
        or randomness_budget is None
        or randomness_envelopes is None
    ):
        raise InvariantError(
            message="Non-deterministic execution missing randomness audit data"
        )
    if approximation is None:
        raise InvariantError(
            message="Non-deterministic execution missing approximation report"
        )
    # derive_metadata validates presence of required ANN metadata surface
    derive_metadata(approximation)


def apply_budget_results(
    session: ExecutionSession,
    approximation: ApproximationReport | None,
    cost: ExecutionCost,
    status: ExecutionStatus,
    failure_reason: str | None,
) -> tuple[ExecutionStatus, str | None]:
    return apply_budget_outcomes(
        session.request,
        approximation,
        cost,
        status,
        failure_reason,
    )


def build_execution_result(
    session: ExecutionSession,
    results_buffer: tuple[Result, ...] | list[Result],
    approximation: ApproximationReport | None,
    cost: ExecutionCost,
    status: ExecutionStatus,
    failure_reason: str | None,
    randomness_sources: tuple[str, ...],
    randomness_budget: tuple[tuple[str, int | float], ...],
    randomness_envelopes: tuple[tuple[str, float], ...],
) -> ExecutionResult:
    signature = execution_signature(
        plan=session.plan,
        corpus_fingerprint=session.artifact.corpus_fingerprint,
        vector_fingerprint=session.artifact.vector_fingerprint,
        randomness=session.randomness,
    )
    determinism_report = None
    if session.request.execution_contract is ExecutionContract.NON_DETERMINISTIC:
        determinism_report = DeterminismReport(
            randomness_sources=randomness_sources,
            reproducibility_bounds=str(session.plan.reproducibility_bounds),
            expected_contract=session.request.execution_contract.value,
            actual_contract=session.request.execution_contract.value,
            notes=(failure_reason,) if failure_reason else (),
        )
    execution_result = ExecutionResult(
        execution_id=session.execution.execution_id,
        signature=signature,
        artifact_id=session.artifact.artifact_id,
        plan=session.plan,
        results=tuple(results_buffer),
        cost=cost,
        approximation=approximation,
        status=status,
        failure_reason=failure_reason,
        randomness_sources=randomness_sources,
        randomness_budget=randomness_budget,
        randomness_envelopes=randomness_envelopes,
        determinism_report=determinism_report,
    )
    if session.request.execution_contract is ExecutionContract.NON_DETERMINISTIC:
        if execution_result.approximation is None:
            raise InvariantError(
                message="Non-deterministic execution missing approximation report"
            )
    else:
        if execution_result.approximation is not None:
            raise InvariantError(
                message="Deterministic execution should not include approximation report"
            )
    return execution_result
