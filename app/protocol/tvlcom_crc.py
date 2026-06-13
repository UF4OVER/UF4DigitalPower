# -*- coding: utf-8 -*-
"""UF4COM CRC helpers."""

from __future__ import annotations


def crc16_ccitt(data: bytes) -> int:
    """CRC16-CCITT used by UF4COM V3."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF
