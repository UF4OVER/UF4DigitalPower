# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: frameBuilder.py
#  @FileType: 协议封装文件，负责帧、载荷和数据类型的编解码
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
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
