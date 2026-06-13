# -*- coding: utf-8 -*-
"""TVLCOM TLV encode/decode helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.const import (
    POWER_DATA_META,
    TYPE_LENGTHS,
    PowerAccess,
    PowerClientAccessError,
    PowerClientProtocolError,
    PowerDataType,
)


@dataclass(frozen=True)
class TvlcomTlvItem:
    type_id: int
    length: int
    raw: bytes
    data_type: PowerDataType | None
    value: int | None


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


def pack_read_request(types: Iterable[PowerDataType]) -> bytes:
    return b"".join(encode_tlv(item) for item in types)
