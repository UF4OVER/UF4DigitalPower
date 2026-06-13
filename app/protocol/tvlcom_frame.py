# -*- coding: utf-8 -*-
"""TVLCOM frame encode/decode helpers."""

from __future__ import annotations

from app.core.const import PowerClientCrcError, PowerClientProtocolError, PowerCommand, SOF

from .tvlcom_crc import crc16_modbus


MAX_PROTOCOL_BODY_LEN = 512


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
