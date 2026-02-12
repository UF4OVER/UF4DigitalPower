# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026 - 01-19 15:10
#  @FileName: parser.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

import struct

from .const import *
from .crc import crc16_ccitt

"""Frame parser for TVLCOM.

Frame format (little-endian):
    SOF(0x7E) | ver:u8 | flags:u8 | seq:u8 | payload_len:u16 | payload | crc16:u16 | EOF(0x7F)

CRC16 is calculated over:
    ver..payload (i.e. frame[1 : 6+payload_len])

Callback contract:
    on_frame(payload: bytes|None, seq: int, flags: int)
- If CRC fails: payload=None and flags includes FLAG_IS_NACK.
- If frame is OK: payload is bytes and flags is the received flags.

This parser consumes bytes incrementally and is friendly to UART streaming.
"""


class FrameParser:
    """Incremental frame parser (byte-by-byte state machine)."""

    def __init__(self, on_frame):
        """Initialize parser with a callback for completed frames.

        Args:
            on_frame (callable): Callback invoked with (payload, seq, flags)
                when a complete and valid frame is received.
        """
        self.on_frame = on_frame
        self.reset()

    def reset(self):
        """Reset the parser state machine."""
        self.state = 0  # NOQA: initial state
        self.buf = bytearray()  # NOQA: initial state
        self.payload_len = 0  # NOQA: initial state

    def feed(self, b: int):
        """Feed a byte to the parser.

        Args:
            b (int): The byte to be processed.
        """
        if self.state == 0:  # SOF
            if b == SOF:
                self.buf = bytearray([b])  # NOQA: initial state
                self.state = 1  # NOQA: initial state

        elif self.state == 1:  # HEADER
            self.buf.append(b)
            if len(self.buf) == 6:
                _, _, _, _, self.payload_len = struct.unpack("<BBBBH", self.buf)  # NOQA
                self.state = 2  # NOQA

        elif self.state == 2:  # PAYLOAD
            self.buf.append(b)
            if len(self.buf) == 6 + self.payload_len:
                self.state = 3  # NOQA

        elif self.state == 3:  # CRC
            self.buf.append(b)
            if len(self.buf) == 6 + self.payload_len + 2:
                self.state = 4  # NOQA

        elif self.state == 4:  # EOF
            if b == EOF:
                self.buf.append(b)
                self._handle(bytes(self.buf))
            self.reset()

    def _handle(self, frame: bytes):
        """Handle a complete frame: verify CRC and invoke the callback.

        Args:
            frame (bytes): The complete frame received.
        """
        sof, ver, flags, seq, plen = struct.unpack("<BBBBH", frame[:6])  # NOQA
        payload = frame[6:6+plen]
        recv_crc = struct.unpack("<H", frame[6+plen:6+plen+2])[0]

        calc_crc = crc16_ccitt(frame[1:6+plen])
        if recv_crc != calc_crc:
            # CRC check failed, invoke callback with NACK flag
            self.on_frame(None, seq, FLAG_IS_NACK)
            return

        # CRC check passed, invoke callback with the payload and flags
        self.on_frame(payload, seq, flags)
