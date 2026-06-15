# -*- coding: utf-8 -*-
"""UF4COM fixed TV encode/decode helpers."""

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
    if raw_value:
        try:
            data_type = PowerDataType(raw_type)
        except ValueError:
            data_type = None
        meta = POWER_DATA_META.get(data_type) if data_type is not None else None
        raw_int = int.from_bytes(raw_value, "little", signed=bool(meta and meta.signed))
        if raw_int < 0:
            raw_int = 0
        if raw_int > 0xFFFF:
            raw_int = 0xFFFF
    else:
        raw_int = 0
    return bytes([raw_type, (raw_int >> 8) & 0xFF, raw_int & 0xFF])


def iter_tlv_items(payload: bytes, *, strict: bool = True) -> list[TvlcomTlvItem]:
    offset = 0
    items: list[TvlcomTlvItem] = []
    while offset < len(payload):
        if offset + 3 > len(payload):
            raise PowerClientProtocolError("Incomplete TV item")

        type_id = payload[offset]
        offset += 1
        raw = payload[offset:offset + 2]
        offset += 2
        length = 2

        try:
            data_type = PowerDataType(type_id)
        except ValueError as exc:
            if strict:
                raise PowerClientProtocolError(f"Unknown data type {type_id}") from exc
            items.append(TvlcomTlvItem(type_id, length, raw, None, None))
            continue

        meta = POWER_DATA_META.get(data_type)
        value = int.from_bytes(raw, "big", signed=False)
        items.append(TvlcomTlvItem(type_id, length, raw, data_type, value))

    return items


def decode_tlvs(payload: bytes, *, strict: bool = True) -> dict[PowerDataType, int]:
    items: dict[PowerDataType, int] = {}
    for item in iter_tlv_items(payload, strict=strict):
        if item.data_type is None or item.value is None:
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
    if len(value) not in (1, 2, 4):
        raise PowerClientProtocolError(
            f"Unexpected write length {len(value)} for {type_id.name}, expected 1, 2, or 4"
        )


def pack_read_request(types: Iterable[PowerDataType]) -> bytes:
    return b"".join(encode_tlv(item) for item in types)
