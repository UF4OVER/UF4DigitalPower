# -*- coding: utf-8 -*-
"""UF4COM frame encode/decode helpers."""

from __future__ import annotations

from app.core.const import PowerClientCrcError, PowerClientProtocolError, PowerCommand, PowerFrameFlag, SOF

from .tvlcom_crc import crc16_ccitt


MAX_PROTOCOL_BODY_LEN = 255
MAX_PROTOCOL_FRAME_LEN = 2 + 1 + 1 + 1 + 1 + MAX_PROTOCOL_BODY_LEN + 2


def build_frame(cmd: PowerCommand | int, seq: int, payload: bytes = b"") -> bytes:
    raw_payload = bytes(payload)
    if len(raw_payload) > MAX_PROTOCOL_BODY_LEN:
        raise PowerClientProtocolError(f"Payload length is too large: {len(raw_payload)}")
    frame = bytearray(SOF)
    frame.extend(
        [
            seq & 0xFF,
            int(PowerFrameFlag.ACK_REQ),
            int(cmd) & 0xFF,
            len(raw_payload) & 0xFF,
        ]
    )
    frame.extend(raw_payload)
    frame.extend(crc16_ccitt(bytes(frame[2:])).to_bytes(2, "little"))
    return bytes(frame)


def extract_frame_from_buffer(
    buffer: bytearray,
    *,
    stream_frame_search: bool = False,
) -> dict[str, int | bytes] | None:
    while len(buffer) >= 2 and buffer[:2] != SOF:
        buffer.pop(0)

    if len(buffer) < 8:
        return None

    payload_len = buffer[5]
    if payload_len > MAX_PROTOCOL_BODY_LEN:
        if stream_frame_search:
            buffer.pop(0)
            return extract_frame_from_buffer(buffer, stream_frame_search=True)
        raise PowerClientProtocolError(f"Payload length is too large: {payload_len}")

    total_len = 2 + 1 + 1 + 1 + 1 + payload_len + 2
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
    actual_crc = crc16_ccitt(raw[2:-2])
    if expected_crc != actual_crc:
        if stream_frame_search:
            buffer[:0] = raw[1:]
            return extract_frame_from_buffer(buffer, stream_frame_search=True)
        raise PowerClientCrcError(
            f"CRC mismatch: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}"
        )

    return {
        "seq": raw[2],
        "flags": raw[3],
        "cmd": raw[4],
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
