# -*- coding: utf-8 -*-
"""TVLCOM raw stream helpers."""

from __future__ import annotations

from typing import Iterable

from app.core.const import (
    STREAM_CHANNEL_SEPARATOR,
    STREAM_VALUE_LENGTHS,
    PowerClientProtocolError,
    PowerDataType,
)

from .tvlcom_tlv import pack_read_request


def _stream_value_length(type_id: PowerDataType) -> int:
    length = STREAM_VALUE_LENGTHS.get(type_id)
    if length is None or length <= 0:
        raise PowerClientProtocolError(f"{type_id.name} cannot be used in raw stream mode")
    return length


def pack_stream_start_request(
    fast_types: Iterable[PowerDataType],
    fast_period_ms: int,
    slow_types: Iterable[PowerDataType] = (),
    slow_period_ms: int = 0,
) -> bytes:
    fast = tuple(fast_types)
    slow = tuple(slow_types)
    fast_period = max(1, min(0xFFFF, int(fast_period_ms)))
    slow_period = max(0, min(0xFFFF, int(slow_period_ms)))
    if not fast:
        raise PowerClientProtocolError("Raw stream requires at least one fast channel")
    if slow and slow_period <= 0:
        raise PowerClientProtocolError("Slow stream period must be positive when slow channels are requested")
    if slow and slow_period % fast_period != 0:
        raise PowerClientProtocolError("Slow stream period must be an integer multiple of fast period")
    return (
        fast_period.to_bytes(2, "little")
        + bytes([len(fast) & 0xFF])
        + pack_read_request(fast)
        + slow_period.to_bytes(2, "little")
        + bytes([len(slow) & 0xFF])
        + pack_read_request(slow)
    )


def stream_sample_size(types: Iterable[PowerDataType]) -> int:
    selected = tuple(types)
    if not selected:
        raise PowerClientProtocolError("Raw stream requires at least one channel")
    value_size = sum(_stream_value_length(type_id) for type_id in selected)
    return value_size + (len(selected) - 1) * len(STREAM_CHANNEL_SEPARATOR)


def decode_stream_sample(sample: bytes, types: Iterable[PowerDataType]) -> dict[PowerDataType, int]:
    selected = tuple(types)
    expected_size = stream_sample_size(selected)
    if len(sample) != expected_size:
        raise PowerClientProtocolError(
            f"Unexpected raw stream sample size {len(sample)}, expected {expected_size}"
        )

    offset = 0
    values: dict[PowerDataType, int] = {}
    for index, type_id in enumerate(selected):
        length = _stream_value_length(type_id)
        raw_value = sample[offset:offset + length]
        offset += length
        values[type_id] = int.from_bytes(raw_value, "little", signed=False)

        if index < len(selected) - 1:
            separator = sample[offset:offset + len(STREAM_CHANNEL_SEPARATOR)]
            if separator != STREAM_CHANNEL_SEPARATOR:
                raise PowerClientProtocolError(
                    f"Raw stream separator mismatch after {type_id.name}: {separator.hex(' ')}"
                )
            offset += len(STREAM_CHANNEL_SEPARATOR)

    return values
