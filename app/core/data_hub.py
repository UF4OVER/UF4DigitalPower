# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: data_hub.py
#  @FileType: 核心基础设施文件，提供设备、数据和通用工具能力
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from typing import Optional, Iterable
import time

from .channel import ChannelConfig
from .ring_buffer import RingBuffer, Sample


class ChannelBuffer:
    """
    单个通道的数据缓存。
    """

    def __init__(self, config: ChannelConfig, max_points: int = 2000):
        self.config = config
        self.buffer = RingBuffer(max_points)

    def append(self, value: float, t: Optional[float] = None) -> None:
        self.buffer.append(value, t)

    def clear(self) -> None:
        self.buffer.clear()

    def latest(self) -> Optional[Sample]:
        return self.buffer.latest()

    def samples(self) -> list[Sample]:
        return self.buffer.samples()

    def window(self, seconds: float, now: Optional[float] = None) -> list[Sample]:
        return self.buffer.window(seconds, now)

    def __len__(self) -> int:
        return len(self.buffer)


class DataHub:
    """
    实时数据中心
    封装数据层哦
    所有设备数据都先进入 DataHub
    图表，仪表盘，日志模块都从 DataHub 取数据
    """

    def __init__(self, default_max_points: int = 2000):
        self.default_max_points = default_max_points
        self._channels: dict[str, ChannelBuffer] = {}

    def register_channel(
        self,
        config: ChannelConfig,
        max_points: Optional[int] = None,
        replace: bool = False,
    ) -> None:
        """
        注册一个数据通道。
        """

        if config.key in self._channels and not replace:
            return

        self._channels[config.key] = ChannelBuffer(
            config=config,
            max_points=max_points or self.default_max_points,
        )

    def register_channels(
        self,
        configs: Iterable[ChannelConfig],
        max_points: Optional[int] = None,
    ) -> None:
        for config in configs:
            self.register_channel(config, max_points=max_points)

    def has_channel(self, key: str) -> bool:
        return key in self._channels

    def get_channel(self, key: str) -> Optional[ChannelBuffer]:
        return self._channels.get(key)

    def channels(self) -> list[ChannelBuffer]:
        return list(self._channels.values())

    def visible_channels(self) -> list[ChannelBuffer]:
        return [
            channel
            for channel in self._channels.values()
            if channel.config.visible
        ]

    def push(self, key: str, value: float, t: Optional[float] = None) -> None:
        """
        写入单个通道数据。
        """

        channel = self._channels.get(key)
        if channel is None:
            return

        channel.append(value, t)

    def push_many(self, data: dict[str, float], t: Optional[float] = None) -> None:
        """
        一次写入多个通道数据。

        例如：
        {
            "vout": 12.05,
            "iout": 2.31,
            "temp": 38.6,
            "power": 27.83,
        }
        """

        if t is None:
            t = time.time()

        for key, value in data.items():
            if value is None:
                continue

            self.push(key, float(value), t)

    def latest_values(self) -> dict[str, float]:
        """
        获取所有通道的最新值。
        """

        result: dict[str, float] = {}

        for key, channel in self._channels.items():
            latest = channel.latest()
            if latest is not None:
                result[key] = latest.value

        return result

    def clear(self, key: Optional[str] = None) -> None:
        """
        清空数据。
        key 为 None 时清空所有通道。
        """

        if key is None:
            for channel in self._channels.values():
                channel.clear()
            return

        channel = self._channels.get(key)
        if channel is not None:
            channel.clear()