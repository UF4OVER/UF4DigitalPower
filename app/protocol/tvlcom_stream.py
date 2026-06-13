# -*- coding: utf-8 -*-
"""UF4COM stream helpers."""

from __future__ import annotations

from typing import Iterable

from app.core.const import (
    PowerClientProtocolError,
    PowerDataType,
)

from .tvlcom_tlv import pack_read_request


def _stream_value_length(type_id: PowerDataType) -> int:
    return 3


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


def stream_sample_size(types: Iterable[PowerDataType]) -> int:
    selected = tuple(types)
    if not selected:
        raise PowerClientProtocolError("UF4COM stream requires at least one channel")
    return sum(_stream_value_length(type_id) for type_id in selected)


def decode_stream_sample(sample: bytes, types: Iterable[PowerDataType]) -> dict[PowerDataType, int]:
    selected = tuple(types)
    expected_size = stream_sample_size(selected)
    if len(sample) != expected_size:
        raise PowerClientProtocolError(
            f"Unexpected raw stream sample size {len(sample)}, expected {expected_size}"
        )

    values: dict[PowerDataType, int] = {}
    for offset in range(0, len(sample), 3):
        type_id_raw = sample[offset]
        value = int.from_bytes(sample[offset + 1:offset + 3], "big", signed=False)
        try:
            type_id = PowerDataType(type_id_raw)
        except ValueError as exc:
            raise PowerClientProtocolError(f"Unknown stream data type {type_id_raw}") from exc
        values[type_id] = value
    return values
