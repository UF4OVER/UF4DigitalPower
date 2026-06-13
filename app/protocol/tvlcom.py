# -*- coding: utf-8 -*-
"""Shared TVLCOM protocol facade used by the power and serial pages."""

from __future__ import annotations

from .tvlcom_crc import crc16_modbus
from .tvlcom_frame import MAX_PROTOCOL_BODY_LEN, TvlcomFrameParser, build_frame, extract_frame_from_buffer
from .tvlcom_stream import decode_stream_sample, pack_stream_start_request, stream_sample_size
from .tvlcom_tlv import (
    TvlcomTlvItem,
    decode_tlvs,
    encode_tlv,
    ensure_readable,
    ensure_writable,
    iter_tlv_items,
    pack_read_request,
)

__all__ = [
    "MAX_PROTOCOL_BODY_LEN",
    "TvlcomFrameParser",
    "TvlcomTlvItem",
    "build_frame",
    "crc16_modbus",
    "decode_stream_sample",
    "decode_tlvs",
    "encode_tlv",
    "ensure_readable",
    "ensure_writable",
    "extract_frame_from_buffer",
    "iter_tlv_items",
    "pack_read_request",
    "pack_stream_start_request",
    "stream_sample_size",
]
