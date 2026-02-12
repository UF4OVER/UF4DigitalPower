# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026 - 01-19 15:10
#  @FileName: frame.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

import struct

from .const import *
from .crc import crc16_ccitt

"""Frame builder for TVLCOM.

build_frame(seq, flags, payload) returns complete frame bytes:
    SOF | ver | flags | seq | payload_len(u16 LE) | payload | crc16 | EOF

CRC16 is calculated over ver..payload: header[1:]+payload.
"""


def build_frame(seq: int, flags: int, payload: bytes) -> bytes:
    header = struct.pack(
        "<BBBBH",
        SOF,
        PROTO_VER,
        flags,
        seq,
        len(payload)
    )

    crc = crc16_ccitt(header[1:] + payload)
    return header + payload + struct.pack("<H", crc) + bytes([EOF])
