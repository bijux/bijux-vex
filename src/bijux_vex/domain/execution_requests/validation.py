# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from bijux_vex.core.contracts.execution_contract import ExecutionContract
from bijux_vex.core.errors import InvariantError
from bijux_vex.core.runtime.execution_session import ExecutionSession
from bijux_vex.infra.adapters.ann_base import AnnExecutionRequestRunner


def require_randomness(
    session: ExecutionSession, ann_runner: AnnExecutionRequestRunner | None
) -> None:
    if (
        session.request.execution_contract is ExecutionContract.NON_DETERMINISTIC
        and session.randomness is None
    ):
        raise InvariantError(
            message="Non-deterministic execution requires randomness in session"
        )
    if (
        session.request.execution_contract is ExecutionContract.NON_DETERMINISTIC
        and ann_runner is None
    ):
        raise InvariantError(message="Approximate execution requires ANN runner")
