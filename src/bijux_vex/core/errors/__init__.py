# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
"""Error taxonomy and retry semantics."""

from __future__ import annotations

from contextlib import suppress

from bijux_vex.core.errors.error_types import (
    AnnBudgetError,
    AnnIndexBuildError,
    AnnQueryError,
    AtomicityViolationError,
    AuthzDeniedError,
    BackendCapabilityError,
    BackendDivergenceError,
    BijuxError,
    BudgetExceededError,
    ConflictError,
    InvariantError,
    NDExecutionUnavailableError,
    NotFoundError,
    ReplayNotSupportedError,
    ValidationError,
    mark_retryable,
)
from bijux_vex.core.failures import (
    FAILURE_ACTIONS,
    FailureKind,
    action_for_failure,
    classify_failure,
    retry_with_policy,
)

_exports = [
    AtomicityViolationError,
    AuthzDeniedError,
    BackendDivergenceError,
    BackendCapabilityError,
    NDExecutionUnavailableError,
    AnnIndexBuildError,
    AnnQueryError,
    AnnBudgetError,
    BijuxError,
    BudgetExceededError,
    ConflictError,
    InvariantError,
    NotFoundError,
    ReplayNotSupportedError,
    ValidationError,
    mark_retryable,
    FailureKind,
    classify_failure,
    retry_with_policy,
    action_for_failure,
]
for sym in _exports:
    with suppress(AttributeError):
        sym.__module__ = __name__
del sym

__all__ = [
    "BijuxError",
    "ValidationError",
    "InvariantError",
    "NotFoundError",
    "ConflictError",
    "AtomicityViolationError",
    "AuthzDeniedError",
    "BackendDivergenceError",
    "BackendCapabilityError",
    "NDExecutionUnavailableError",
    "AnnIndexBuildError",
    "AnnQueryError",
    "AnnBudgetError",
    "ReplayNotSupportedError",
    "BudgetExceededError",
    "mark_retryable",
    "FailureKind",
    "classify_failure",
    "retry_with_policy",
    "FAILURE_ACTIONS",
    "action_for_failure",
]
