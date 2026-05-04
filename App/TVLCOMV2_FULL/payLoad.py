# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026/4/9
#  @FileName: payLoad.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from .dataType import TypeBase, TYPE_REGISTRY

CMD_ACK = 0x00
CMD_NACK = 0xFF

class Payload:
    def __init__(self):
        self.buf = bytearray()

    def addData(self, _type: TypeBase, value):
        valueBytes = _type.encode(value)
        length = len(valueBytes)

        if length > 0xFFFF:
            raise ValueError("TLV too large")

        self.buf.append(_type.typeId)
        self.buf.append(length & 0xFF)
        self.buf.append((length >> 8) & 0xFF)
        self.buf.extend(valueBytes)

    def toBytes(self):
        return bytes(self.buf)

    def clear(self):
        self.buf.clear()

    def __str__(self):
        return " ".join(f"{b:02X}" for b in self.buf)

    @staticmethod
    def parse(data: bytes):
        offset = 0
        result = {}

        while offset < len(data):
            typeId = data[offset]
            offset += 1

            length = data[offset] | (data[offset + 1] << 8)
            offset += 2

            valueBytes = data[offset:offset + length]
            offset += length

            if typeId in TYPE_REGISTRY:
                result[typeId] = TYPE_REGISTRY[typeId].decode(valueBytes)
            else:
                result[typeId] = valueBytes

        return result

class Dispatcher:
    def __init__(self):
        self.handlers = {}
        self.ackHandler = None
        self.nackHandler = None

    def registerHandler(self, cmd, func):
        if cmd in (CMD_ACK, CMD_NACK):
            raise ValueError("CMD_ACK/CMD_NACK are reserved control commands")
        self.handlers[cmd] = func

    def setAckHandler(self, func=None):
        self.ackHandler = func

    def setNackHandler(self, func=None):
        self.nackHandler = func

    def dispatch(self, frame):
        cmd = frame["cmd"]
        payloadData = Payload.parse(frame["payload"])

        if cmd == CMD_ACK:
            if self.ackHandler is not None:
                self.ackHandler(cmd, frame["seq"], payloadData)
                return True
            return False

        if cmd == CMD_NACK:
            if self.nackHandler is not None:
                self.nackHandler(cmd, frame["seq"], payloadData)
                return True
            return False

        if cmd in self.handlers:
            self.handlers[cmd](frame["seq"], payloadData)
            return True

        return False
