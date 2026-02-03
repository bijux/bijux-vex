# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bijux_vex.infra.plugins.contract import PluginContract
from bijux_vex.infra.plugins.entrypoints import load_entrypoints


@dataclass(frozen=True)
class RunnerDescriptor:
    name: str


RunnerFactory = Callable[[], object]


class RunnerRegistry:
    def __init__(self) -> None:
        self._runners: dict[str, tuple[RunnerFactory, PluginContract]] = {}

    def register(
        self, name: str, *, factory: RunnerFactory, contract: PluginContract
    ) -> None:
        if not contract.determinism:
            raise ValueError("Runner contract must declare determinism")
        if contract.randomness_sources is None:
            raise ValueError("Runner contract must declare randomness sources")
        self._runners[name] = (factory, contract)

    def available(self) -> list[str]:
        return sorted(self._runners.keys())


RUNNERS = RunnerRegistry()
load_entrypoints("bijux_vex.runners", RUNNERS)


__all__ = ["RunnerRegistry", "RunnerDescriptor", "RUNNERS"]
