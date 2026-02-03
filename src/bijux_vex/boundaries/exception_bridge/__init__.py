# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from bijux_vex.core import errors
from bijux_vex.infra.metrics import METRICS

HTTP_MAPPING: dict[type[BaseException], int] = {
    errors.ValidationError: 400,
    errors.InvariantError: 422,
    errors.NotFoundError: 404,
    errors.ConflictError: 409,
    errors.ConfigurationError: 400,
    errors.DeterminismViolationError: 422,
    errors.BackendUnavailableError: 503,
    errors.CorruptArtifactError: 500,
    errors.AuthzDeniedError: 403,
    errors.AtomicityViolationError: 409,
    errors.BackendDivergenceError: 500,
    errors.BackendCapabilityError: 422,
    errors.AnnIndexBuildError: 500,
    errors.AnnQueryError: 500,
    errors.AnnBudgetError: 422,
    errors.ReplayNotSupportedError: 422,
    errors.PluginLoadError: 500,
    errors.PluginTimeoutError: 500,
}

CLI_EXIT_MAPPING: dict[type[BaseException], int] = {
    errors.ValidationError: 2,
    errors.InvariantError: 3,
    errors.NotFoundError: 4,
    errors.ConflictError: 5,
    errors.ConfigurationError: 2,
    errors.DeterminismViolationError: 13,
    errors.BackendUnavailableError: 14,
    errors.CorruptArtifactError: 15,
    errors.AuthzDeniedError: 6,
    errors.AtomicityViolationError: 7,
    errors.BackendDivergenceError: 8,
    errors.BackendCapabilityError: 9,
    errors.AnnIndexBuildError: 10,
    errors.AnnQueryError: 11,
    errors.AnnBudgetError: 12,
    errors.ReplayNotSupportedError: 9,
    errors.PluginLoadError: 16,
    errors.PluginTimeoutError: 17,
}


def to_http_status(exc: Exception) -> int:
    for exc_type, status in HTTP_MAPPING.items():
        if isinstance(exc, exc_type):
            return status
    raise exc


def to_cli_exit(exc: Exception) -> int:
    for exc_type, code in CLI_EXIT_MAPPING.items():
        if isinstance(exc, exc_type):
            return code
    raise exc


def is_refusal(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            errors.ConfigurationError,
            errors.DeterminismViolationError,
            errors.BackendUnavailableError,
            errors.BackendCapabilityError,
        ),
    )


def refusal_payload(exc: Exception) -> dict[str, object]:
    if isinstance(exc, errors.DeterminismViolationError):
        return {
            "reason": "determinism_violation",
            "message": str(exc),
            "remediation": "Use deterministic inputs or switch to non_deterministic contract with declared randomness.",
        }
    if isinstance(exc, errors.BackendCapabilityError):
        return {
            "reason": "backend_capability_missing",
            "message": str(exc),
            "remediation": "Select a backend that supports the requested capability or change the request.",
        }
    if isinstance(exc, errors.BackendUnavailableError):
        return {
            "reason": "backend_unavailable",
            "message": str(exc),
            "remediation": "Verify backend connectivity/credentials and retry.",
        }
    if isinstance(exc, errors.ConfigurationError):
        return {
            "reason": "configuration_error",
            "message": str(exc),
            "remediation": "Fix configuration and retry.",
        }
    return {"reason": "unknown", "message": str(exc), "remediation": "Inspect logs."}


def record_failure(exc: Exception) -> None:
    if isinstance(
        exc,
        (
            errors.BackendUnavailableError,
            errors.BackendCapabilityError,
            errors.BackendDivergenceError,
        ),
    ):
        METRICS.increment("backend_failures_total", 1)
