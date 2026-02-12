# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026 - 01-19 15:10
#  @FileName: dispatcher.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from .const import *
from .frame import build_frame

"""TLV dispatcher for TVLCOM payloads.

Responsibilities:
- Optionally auto-reply ACK if FLAG_ACK_REQ is set.
- Split payload into TLVs and call registered handlers.

Handler signature:
    cb(value_bytes, seq)
"""


class Dispatcher:
    """Dispatches TLV entries to per-type callbacks."""

    def __init__(self, send_func):
        self.send = send_func
        self.handlers = {}

    def register(self, tlv_type, cb):
        self.handlers[tlv_type] = cb

    def handle_frame(self, payload, seq, flags):
        if flags & FLAG_IS_ACK:
            return
        if flags & FLAG_IS_NACK:
            return

        if flags & FLAG_ACK_REQ:
            self.send(build_frame(seq, FLAG_IS_ACK, b""))

        if not payload:
            return

        off = 0
        while off + 3 <= len(payload):
            t = payload[off]
            l = int.from_bytes(payload[off+1:off+3], "little")
            v = payload[off+3:off+3+l]

            if t in self.handlers:
                self.handlers[t](v, seq)

            off += 3 + l
