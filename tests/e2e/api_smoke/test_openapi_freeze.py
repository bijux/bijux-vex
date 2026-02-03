# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
from fastapi.encoders import jsonable_encoder

from bijux_vex.boundaries.api.app import build_app
from bijux_vex.core.canon import canon
from bijux_vex.core.identity.ids import fingerprint

EXPECTED_OPENAPI_FINGERPRINT = (
    "1f93134273427d8f19111926ef790541ef36b5a1a4e9541ecb2c5f2d260f2737"
)


def test_openapi_schema_is_frozen():
    app = build_app()
    schema = jsonable_encoder(app.openapi())
    fp = fingerprint(canon(schema))
    assert fp == EXPECTED_OPENAPI_FINGERPRINT
