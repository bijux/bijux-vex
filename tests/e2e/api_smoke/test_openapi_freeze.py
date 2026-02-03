# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
from fastapi.encoders import jsonable_encoder

from bijux_vex.boundaries.api.app import build_app
from bijux_vex.core.canon import canon
from bijux_vex.core.identity.ids import fingerprint

EXPECTED_OPENAPI_FINGERPRINT = (
    "e05e6e0bd32d501bb132ee9b784bb07c02770641637ac2d74955b3c46b8f5bed"
)


def test_openapi_schema_is_frozen():
    app = build_app()
    schema = jsonable_encoder(app.openapi())
    fp = fingerprint(canon(schema))
    assert fp == EXPECTED_OPENAPI_FINGERPRINT
