# -*- coding: utf-8 -*-
"""Shared TVLCOM frame/TLV helpers used by the power and serial pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.const import (
    POWER_DATA_META,
    PowerAccess,
    PowerClientAccessError,
    PowerClientCrcError,
    PowerClientProtocolError,
    PowerCommand,
    PowerDataType,
    SOF,
    STREAM_CHANNEL_SEPARATOR,
    STREAM_VALUE_LENGTHS,
    TYPE_LENGTHS,
)


MAX_PROTOCOL_BODY_LEN = 512


@dataclass(frozen=True)
class TvlcomTlvItem:
    type_id: int
    length: int
    raw: bytes
    data_type: PowerDataType | None
    value: int | None


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def encode_tlv(type_id: PowerDataType | int, value: bytes = b"") -> bytes:
    raw_type = int(type_id) & 0xFF
    raw_value = bytes(value)
    return bytes([raw_type]) + len(raw_value).to_bytes(2, "little") + raw_value


def iter_tlv_items(payload: bytes, *, strict: bool = True) -> list[TvlcomTlvItem]:
    offset = 0
    items: list[TvlcomTlvItem] = []
    while offset < len(payload):
        if offset + 3 > len(payload):
            raise PowerClientProtocolError("Incomplete TLV header")

        type_id = payload[offset]
        offset += 1
        length = int.from_bytes(payload[offset:offset + 2], "little")
        offset += 2

        if offset + length > len(payload):
            raise PowerClientProtocolError(f"Incomplete TLV value for type {type_id}")

        raw = payload[offset:offset + length]
        offset += length

        try:
            data_type = PowerDataType(type_id)
        except ValueError as exc:
            if strict:
                raise PowerClientProtocolError(f"Unknown data type {type_id}") from exc
            items.append(TvlcomTlvItem(type_id, length, raw, None, None))
            continue

        expected_length = TYPE_LENGTHS.get(data_type)
        if expected_length is not None and length not in (0, expected_length):
            if strict:
                raise PowerClientProtocolError(
                    f"Unexpected length {length} for {data_type.name}, expected {expected_length}"
                )
            items.append(TvlcomTlvItem(type_id, length, raw, data_type, None))
            continue

        meta = POWER_DATA_META.get(data_type)
        value = None
        if length:
            value = int.from_bytes(raw, "little", signed=bool(meta and meta.signed))
        items.append(TvlcomTlvItem(type_id, length, raw, data_type, value))

    return items


def decode_tlvs(payload: bytes, *, strict: bool = True) -> dict[PowerDataType, int]:
    items: dict[PowerDataType, int] = {}
    for item in iter_tlv_items(payload, strict=strict):
        if item.data_type is None or item.value is None:
            if strict and item.length == 0:
                raise PowerClientProtocolError(f"Missing TLV value for type {item.type_id}")
            continue
        items[item.data_type] = item.value
    return items


def ensure_readable(type_id: PowerDataType) -> None:
    meta = POWER_DATA_META.get(type_id)
    if meta is not None and not (int(meta.access) & int(PowerAccess.READ)):
        raise PowerClientAccessError(f"{type_id.name} is not readable")


def ensure_writable(type_id: PowerDataType, value: bytes) -> None:
    meta = POWER_DATA_META.get(type_id)
    if meta is None:
        raise PowerClientAccessError(f"{type_id.name} has no writable metadata")
    if not (int(meta.access) & int(PowerAccess.WRITE)):
        raise PowerClientAccessError(f"{type_id.name} is not writable")
    if len(value) != meta.length:
        raise PowerClientProtocolError(
            f"Unexpected write length {len(value)} for {type_id.name}, expected {meta.length}"
        )


def build_frame(cmd: PowerCommand | int, seq: int, payload: bytes = b"") -> bytes:
    body = bytes([int(cmd) & 0xFF, seq & 0xFF]) + payload
    frame = bytearray(SOF)
    frame.extend(len(body).to_bytes(2, "little"))
    frame.extend(body)
    frame.extend(crc16_modbus(frame).to_bytes(2, "little"))
    return bytes(frame)


def extract_frame_from_buffer(
    buffer: bytearray,
    *,
    stream_frame_search: bool = False,
) -> dict[str, int | bytes] | None:
    while len(buffer) >= 2 and buffer[:2] != SOF:
        buffer.pop(0)

    if len(buffer) < 6:
        return None

    body_len = int.from_bytes(buffer[2:4], "little")
    if body_len > MAX_PROTOCOL_BODY_LEN:
        if stream_frame_search:
            buffer.pop(0)
            return extract_frame_from_buffer(buffer, stream_frame_search=True)
        raise PowerClientProtocolError(f"Body length is too large: {body_len}")

    total_len = 2 + 2 + body_len + 2
    if len(buffer) < total_len:
        if stream_frame_search:
            next_sof = buffer.find(SOF, 1)
            if next_sof > 0:
                del buffer[:next_sof]
                return extract_frame_from_buffer(buffer, stream_frame_search=True)
        return None

    raw = bytes(buffer[:total_len])
    del buffer[:total_len]

    expected_crc = int.from_bytes(raw[-2:], "little")
    actual_crc = crc16_modbus(raw[:-2])
    if expected_crc != actual_crc:
        if stream_frame_search:
            buffer[:0] = raw[1:]
            return extract_frame_from_buffer(buffer, stream_frame_search=True)
        raise PowerClientCrcError(
            f"CRC mismatch: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}"
        )

    if body_len < 2:
        if stream_frame_search:
            buffer[:0] = raw[1:]
            return extract_frame_from_buffer(buffer, stream_frame_search=True)
        raise PowerClientProtocolError("Body length is too short")

    return {
        "cmd": raw[4],
        "seq": raw[5],
        "payload": raw[6:-2],
    }


class TvlcomFrameParser:
    def __init__(self):
        self.buffer = bytearray()

    def input_bytes(self, data: bytes) -> list[dict[str, int | bytes]]:
        self.buffer.extend(data)
        frames: list[dict[str, int | bytes]] = []
        while True:
            frame = extract_frame_from_buffer(self.buffer)
            if frame is None:
                break
            frames.append(frame)
        return frames


def pack_read_request(types: Iterable[PowerDataType]) -> bytes:
    return b"".join(encode_tlv(item) for item in types)


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
