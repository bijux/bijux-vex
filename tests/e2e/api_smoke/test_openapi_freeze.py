# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations
from fastapi.encoders import jsonable_encoder

from bijux_vex.boundaries.api.app import build_app
from bijux_vex.core.canon import canon
from bijux_vex.core.identity.ids import fingerprint

EXPECTED_OPENAPI_FINGERPRINT = (
    "fdbe91b9e57e485a401e25c239674574d2dd3c867ff8593603ceb60154a93c9c"
)


def test_openapi_schema_is_frozen():
    app = build_app()
    schema = jsonable_encoder(app.openapi())
    fp = fingerprint(canon(schema))
    assert fp == EXPECTED_OPENAPI_FINGERPRINT
