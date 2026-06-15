# -*- coding: utf-8 -*-
"""UF4COM stream helpers."""

from __future__ import annotations

from typing import Iterable

from app.core.const import (
    PowerClientProtocolError,
    PowerDataType,
)

from .tvlcom_tlv import pack_read_request


def pack_stream_start_request(
    fast_types: Iterable[PowerDataType],
    fast_period_ms: int,
    slow_types: Iterable[PowerDataType] = (),
    slow_period_ms: int = 0,
) -> bytes:
    fast = tuple(fast_types)
    slow = tuple(slow_types)
    if not fast:
        raise PowerClientProtocolError("UF4COM stream requires at least one channel")
    return pack_read_request(fast + slow)
