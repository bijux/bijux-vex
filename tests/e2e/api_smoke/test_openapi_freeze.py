# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
from fastapi.encoders import jsonable_encoder

from bijux_vex.boundaries.api.app import build_app
from bijux_vex.core.canon import canon
from bijux_vex.core.identity.ids import fingerprint

EXPECTED_OPENAPI_FINGERPRINT = (
    "6a3952bd3c927a3bea9a32f6b7b0e259147a7a19833c28d81b754ea29ee902a7"
)


def test_openapi_schema_is_frozen():
    app = build_app()
    schema = jsonable_encoder(app.openapi())
    fp = fingerprint(canon(schema))
    assert fp == EXPECTED_OPENAPI_FINGERPRINT
