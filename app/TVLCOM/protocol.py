# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026 - 01-19 15:11
#  @FileName: protocol.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from .const import FLAG_ACK_REQ
from .dispatcher import Dispatcher
from .frame import build_frame
from .parser import FrameParser

"""High-level protocol wrapper.

Protocol ties together:
- FrameParser: bytes -> (payload, seq, flags)
- Dispatcher: payload TLV dispatch + auto ACK
- build_frame: payload -> raw bytes to put on UART

You provide send_func(bytes) which actually writes to the transport.
"""


class Protocol:
    """TVLCOM protocol endpoint (works for PC, MCU, MicroPython)."""

    def __init__(self, send_func):
        self.seq = 0
        self.send = send_func
        self.dispatcher = Dispatcher(send_func)
        self.parser = FrameParser(self.dispatcher.handle_frame)

    def feed(self, data: bytes):
        for b in data:
            self.parser.feed(b)

    def send_payload(self, payload: bytes, ack=True):
        flags = FLAG_ACK_REQ if ack else 0
        frame = build_frame(self.seq, flags, payload)
        self.send(frame)
        self.seq = (self.seq + 1) & 0xFF
