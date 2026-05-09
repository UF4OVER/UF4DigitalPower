# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : TVLCOM
#  @Time    : 2026/4/9
#  @FileName: frameParser.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from .unitls import crc16, SOF

class FrameParser:
    def __init__(self):
        self.buffer = bytearray()

    def inputBytes(self, data: bytes):
        self.buffer.extend(data)
        frames = []

        while True:
            if len(self.buffer) < 6:
                break

            if self.buffer[0:2] != SOF:
                self.buffer.pop(0)
                continue

            length = self.buffer[2] | (self.buffer[3] << 8)
            total_len = 2 + 2 + length + 2

            if len(self.buffer) < total_len:
                break

            frame = self.buffer[:total_len]
            self.buffer = self.buffer[total_len:]

            recv_crc = frame[-2] | (frame[-1] << 8)
            calc_crc = crc16(frame[:-2])

            if recv_crc != calc_crc:
                continue

            cmd = frame[4]
            seq = frame[5]
            payload = frame[6:-2]

            frames.append({
                "cmd": cmd,
                "seq": seq,
                "payload": payload
            })

        return frames


