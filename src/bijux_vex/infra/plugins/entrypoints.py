# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from importlib import metadata
import logging
from typing import Any


def load_entrypoints(group: str, registry: Any) -> None:
    entries = []
    try:
        entries = list(metadata.entry_points(group=group))
    except TypeError:  # pragma: no cover - compatibility
        all_eps = metadata.entry_points()
        if hasattr(all_eps, "select"):
            entries = list(all_eps.select(group=group))
        else:
            entries = list(all_eps.get(group, []))
    for ep in entries:
        try:
            plugin = ep.load()
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "Failed to load entrypoint %s for group %s: %s", ep, group, exc
            )
            continue
        _register_plugin(plugin, registry)


def _register_plugin(plugin: Any, registry: Any) -> None:
    if hasattr(plugin, "register") and callable(plugin.register):
        plugin.register(registry)
        return
    if callable(plugin):
        plugin(registry)
        return


__all__ = ["load_entrypoints"]
