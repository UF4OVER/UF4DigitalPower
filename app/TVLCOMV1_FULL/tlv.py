# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOMV1_FULL
#  @Time    : 2026 - 01-19 15:09
#  @FileName: tlv.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

import struct

from .const import *

"""TLV helpers.

TLV encoding used by TVLCOMV1_FULL payloads:
    type:u8 | length:u16 (little-endian) | value:bytes

This module provides convenience encoders for common scalar types.
"""

def tlv_encode(t: int, value: bytes) -> bytes:
    return struct.pack("<BH", t, len(value)) + value

def tlv_string(s: str) -> bytes:
    return tlv_encode(TLV_STRING, s.encode())

def tlv_int32(v: int) -> bytes:
    return tlv_encode(TLV_INT32, struct.pack("<i", v))

def tlv_uint32(v: int) -> bytes:
    return tlv_encode(TLV_UINT32, struct.pack("<I", v))

def tlv_float(v: float) -> bytes:
    return tlv_encode(TLV_FLOAT, struct.pack("<f", v))
