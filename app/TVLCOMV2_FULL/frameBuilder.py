# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026/4/9
#  @FileName: frameBuilder.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from .unitls import crc16, SOF

class FrameBuilder:
    @staticmethod
    def buildFrame(cmd, seq, payloadBytes: bytes):
        body = bytes([cmd, seq]) + payloadBytes
        length = len(body)

        frame = bytearray()
        frame.extend(SOF)
        frame.append(length & 0xFF)
        frame.append((length >> 8) & 0xFF)
        frame.extend(body)

        crc = crc16(frame)
        frame.append(crc & 0xFF)
        frame.append((crc >> 8) & 0xFF)

        return bytes(frame)
