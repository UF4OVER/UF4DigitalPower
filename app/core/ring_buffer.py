# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: ring_buffer.py
#  @FileType: 核心基础设施文件，提供设备、数据和通用工具能力
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, Iterable, Optional
import time


@dataclass(frozen=True)
class Sample:
    """
    单个采样点。
    t: 时间戳，单位秒，通常使用 time.time()
    value: 采样值
    """

    t: float
    value: float


class RingBuffer:
    """
    固定长度环形缓冲区。
    """

    def __init__(self, maxlen: int = 2000):
        if maxlen <= 0:
            raise ValueError("maxlen must be greater than 0")

        self._data: Deque[Sample] = deque(maxlen=maxlen)

    @property
    def maxlen(self) -> int:
        """
        满了直接丢了，最大点数
        """
        return self._data.maxlen or 0

    def append(self, value: float, t: Optional[float] = None) -> None:
        if t is None:
            t = time.time()

        self._data.append(Sample(float(t), float(value)))

    def extend(self, samples: Iterable[Sample]) -> None:
        for sample in samples:
            self._data.append(sample)

    def clear(self) -> None:
        self._data.clear()

    def samples(self) -> list[Sample]:
        return list(self._data)

    def latest(self) -> Optional[Sample]:
        if not self._data:
            return None
        return self._data[-1]

    def values(self) -> list[float]:
        return [sample.value for sample in self._data]

    def times(self) -> list[float]:
        return [sample.t for sample in self._data]

    def window(self, seconds: float, now: Optional[float] = None) -> list[Sample]:
        """
        返回最近 seconds 秒的数据。
        """

        if seconds <= 0:
            return []

        if now is None:
            now = time.time()

        min_t = now - seconds
        result: list[Sample] = []
        for sample in reversed(self._data):
            if sample.t < min_t:
                break
            result.append(sample)
        result.reverse()
        return result

    def __len__(self) -> int:
        return len(self._data)

    def __bool__(self) -> bool:
        return bool(self._data)
