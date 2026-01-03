# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from bijux_vex.contracts.resources import ExecutionResources
from bijux_vex.core.errors import BijuxError
from bijux_vex.core.execution_result import ExecutionResult
from bijux_vex.core.runtime.vector_execution import RandomnessProfile
from bijux_vex.core.types import ExecutionArtifact, ExecutionRequest, Result
from bijux_vex.domain.execution_requests.budget import (
    apply_budget_outcomes,
)
from bijux_vex.domain.execution_requests.execution import collect_results, estimate_cost
from bijux_vex.domain.execution_requests.planning import start_session
from bijux_vex.domain.execution_requests.postprocess import (
    build_execution_result,
    guard_nd_randomness,
    randomness_audit,
)
from bijux_vex.domain.execution_requests.validation import require_randomness
from bijux_vex.infra.adapters.ann_base import AnnExecutionRequestRunner


def start_execution_session(
    artifact: ExecutionArtifact,
    request: ExecutionRequest,
    resources: ExecutionResources,
    randomness: RandomnessProfile | None = None,
    ann_runner: AnnExecutionRequestRunner | None = None,
) -> ExecutionSession:
    return start_session(
        artifact=artifact,
        request=request,
        resources=resources,
        randomness=randomness,
        ann_runner=ann_runner,
    )


def execute_request(
    session: ExecutionSession,
    resources: ExecutionResources,
    ann_runner: AnnExecutionRequestRunner | None = None,
) -> tuple[ExecutionResult, Iterable[Result]]:
    require_randomness(session, ann_runner)
    results_buffer, status, failure_reason, approximation = collect_results(
        session, resources, ann_runner
    )
    cost = estimate_cost(session.request, results_buffer)
    status, failure_reason = apply_budget_outcomes(
        session.request, approximation, cost, status, failure_reason
    )
    randomness_sources, randomness_budget, randomness_envelopes = randomness_audit(
        session
    )
    guard_nd_randomness(
        session,
        randomness_sources,
        randomness_budget,
        randomness_envelopes,
        approximation,
    )
    execution_result = build_execution_result(
        session=session,
        results_buffer=results_buffer,
        approximation=approximation,
        cost=cost,
        status=status,
        failure_reason=failure_reason,
        randomness_sources=randomness_sources,
        randomness_budget=randomness_budget,
        randomness_envelopes=randomness_envelopes,
    )
    return execution_result, tuple(results_buffer)


# Re-export for compatibility
from bijux_vex.core.runtime.execution_session import ExecutionSession  # noqa: E402

__all__ = ["start_execution_session", "execute_request", "ExecutionSession"]


@dataclass(frozen=True)
class ExecutionOutcome:
    result: ExecutionResult | None
    failure: BijuxError | None


def execute_request_outcome(
    session: ExecutionSession,
    resources: ExecutionResources,
    ann_runner: AnnExecutionRequestRunner | None = None,
) -> ExecutionOutcome:
    try:
        result, results = execute_request(session, resources, ann_runner=ann_runner)
        return ExecutionOutcome(result=result, failure=None)
    except BijuxError as exc:  # value-based error surface
        return ExecutionOutcome(result=None, failure=exc)
