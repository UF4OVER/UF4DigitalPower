# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: chart_model.py
#  @FileType: 图表组件文件，负责实时曲线、图表模型和数据展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import time

from app.core.data_hub import DataHub, ChannelBuffer
from app.core.ring_buffer import Sample


@dataclass
class AxisRange:
    """
    坐标轴范围。
    """
    minimum: float
    maximum: float

    @property
    def span(self) -> float:
        return self.maximum - self.minimum

    def is_valid(self) -> bool:
        return self.maximum > self.minimum

    def expand_ratio(self, ratio: float) -> "AxisRange":
        """
        按比例向上下扩展范围。
        例如 ratio=0.1 表示上下各扩展 10%。
        """

        if not self.is_valid():
            return self

        delta = self.span * ratio
        return AxisRange(
            self.minimum - delta,
            self.maximum + delta,
        )


@dataclass
class ChartPoint:
    """
    图表点。

    raw_x/raw_y 是真实数据坐标。
    gl_x/gl_y 是归一化坐标，范围通常是 -1.0 到 1.0。
    """
    raw_x: float
    raw_y: float
    gl_x: float
    gl_y: float


@dataclass
class ChartCurve:
    key: str
    name: str
    unit: str
    precision: int
    points: list[ChartPoint]


@dataclass
class ChartSnapshot:
    """
    某一帧图表快照。

    渲染层直接消费这个结构。
    """
    x_range: AxisRange
    y_range: AxisRange
    curves: list[ChartCurve]



class ChartModel:
    """
    图表模型层。

    职责：
    - 从 DataHub 获取通道数据
    - 截取最近 N 秒采样点
    - 自动计算 Y 轴范围
    - 把真实坐标转换为归一化坐标
    """

    def __init__(self, data_hub: DataHub):
        self.data_hub = data_hub

        self.time_window_sec: float = 10.0
        self.time_offset_sec: float = 0.0

        self.auto_y_range: bool = True

        self.manual_y_range = AxisRange(0.0, 1.0)
        self.y_padding_ratio: float = 0.1

        self.visible_groups: set[str] | None = None
        self.selected_channels: set[str] | None = None

    def set_time_window(self, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("time window must be greater than 0")

        self.time_window_sec = float(seconds)

    def set_auto_y_range(self, enabled: bool) -> None:
        self.auto_y_range = bool(enabled)

    def set_manual_y_range(self, minimum: float, maximum: float) -> None:
        if maximum <= minimum:
            raise ValueError("maximum must be greater than minimum")

        self.manual_y_range = AxisRange(float(minimum), float(maximum))
        self.auto_y_range = False

    def build_snapshot(self, now: Optional[float] = None) -> ChartSnapshot:
        return self.build_snapshot_for_width(None, now=now)

    def build_snapshot_for_width(
        self,
        pixel_width: int | None,
        now: Optional[float] = None,
    ) -> ChartSnapshot:
        if now is None:
            now = time.time()

        view_now = now + self.time_offset_sec  # 偏移

        x_range = AxisRange(
            minimum=view_now - self.time_window_sec,
            maximum=view_now,
        )

        visible_channels = self._filter_visible_channels()
        channel_samples = self._collect_window_samples(
            visible_channels,
            self.time_window_sec,
            view_now,
        )
        reduced_channel_samples = [
            (channel, self._downsample_samples(samples, pixel_width))
            for channel, samples in channel_samples
        ]

        y_range = self._calculate_y_range(reduced_channel_samples)

        curves: list[ChartCurve] = []

        for channel, samples in reduced_channel_samples:
            points = [
                self._to_chart_point(sample, x_range, y_range)
                for sample in samples
            ]

            curves.append(
                ChartCurve(
                    key=channel.config.key,
                    name=channel.config.name,
                    unit=channel.config.unit,
                    precision=channel.config.precision,
                    points=points,
                )
            )

        return ChartSnapshot(
            x_range=x_range,
            y_range=y_range,
            curves=curves,
        )

    @staticmethod
    def _downsample_samples(samples: list[Sample], pixel_width: int | None) -> list[Sample]:
        if pixel_width is None or pixel_width <= 0:
            return samples

        target_points = max(2, int(pixel_width) * 2)
        if len(samples) <= target_points:
            return samples

        bucket_count = max(1, int(pixel_width))
        bucket_size = len(samples) / bucket_count
        reduced: list[Sample] = []

        for bucket_index in range(bucket_count):
            start = int(bucket_index * bucket_size)
            end = max(start + 1, int((bucket_index + 1) * bucket_size))
            bucket = samples[start:end]
            if not bucket:
                continue
            if len(bucket) <= 2:
                reduced.extend(bucket)
                continue

            minimum = min(bucket, key=lambda item: item.value)
            maximum = max(bucket, key=lambda item: item.value)
            if minimum.t <= maximum.t:
                reduced.extend((minimum, maximum))
            else:
                reduced.extend((maximum, minimum))

        if not reduced:
            return [samples[0], samples[-1]]

        first = samples[0]
        last = samples[-1]
        if reduced[0] != first:
            reduced.insert(0, first)
        if reduced[-1] != last:
            reduced.append(last)
        return reduced

    @staticmethod
    def pixel_to_time(pixel_x: int, pixel_width: int, x_range: AxisRange) -> float:
        if pixel_width <= 1 or not x_range.is_valid():
            return x_range.maximum

        ratio = max(0.0, min(1.0, pixel_x / max(1, pixel_width)))
        return x_range.minimum + x_range.span * ratio

    @staticmethod
    def point_to_pixel_x(point: ChartPoint, pixel_width: int) -> int:
        return int((point.gl_x + 1.0) * 0.5 * pixel_width)

    def _filter_visible_channels(self) -> list[ChannelBuffer]:
        channels = self.data_hub.visible_channels()

        if self.visible_groups is not None:
            channels = [
                channel
                for channel in channels
                if channel.config.group in self.visible_groups
            ]

        if self.selected_channels is not None:
            channels = [
                channel
                for channel in channels
                if channel.config.key in self.selected_channels
            ]

        return channels

    def _collect_window_samples(
        self,
        channels: list[ChannelBuffer],
        seconds: float,
        now: float,
    ) -> list[tuple[ChannelBuffer, list[Sample]]]:
        result: list[tuple[ChannelBuffer, list[Sample]]] = []

        for channel in channels:
            samples = channel.window(seconds, now)
            result.append((channel, samples))

        return result

    def _calculate_y_range(
        self,
        channel_samples: list[tuple[ChannelBuffer, list[Sample]]],
    ) -> AxisRange:
        if not self.auto_y_range:
            return self.manual_y_range

        values: list[float] = []

        for _, samples in channel_samples:
            for sample in samples:
                values.append(sample.value)

        if not values:
            return AxisRange(0.0, 1.0)

        minimum = min(values)
        maximum = max(values)

        if maximum == minimum:
            center = maximum
            return AxisRange(center - 1.0, center + 1.0)

        return AxisRange(minimum, maximum).expand_ratio(self.y_padding_ratio)

    @staticmethod
    def _to_chart_point(
        sample: Sample,
        x_range: AxisRange,
        y_range: AxisRange,
    ) -> ChartPoint:
        gl_x = ChartModel._map_to_gl(sample.t, x_range)
        gl_y = ChartModel._map_to_gl(sample.value, y_range)

        return ChartPoint(
            raw_x=sample.t,
            raw_y=sample.value,
            gl_x=gl_x,
            gl_y=gl_y,
        )

    @staticmethod
    def _map_to_gl(value: float, axis_range: AxisRange) -> float:
        if not axis_range.is_valid():
            return 0.0

        normalized = (value - axis_range.minimum) / axis_range.span
        return normalized * 2.0 - 1.0

    def set_visible_groups(self, groups: set[str] | list[str] | tuple[str, ...] | None) -> None:
        """
        设置当前图表显示哪些分组。

        groups 为 None 表示显示所有可见通道。
        """
        if groups is None:
            self.visible_groups = None
        else:
            self.visible_groups = set(groups)

    def show_group(self, group: str) -> None:
        """
        只显示一个分组。
        """
        self.visible_groups = {group}

    def show_all_groups(self) -> None:
        """
        显示所有分组。
        """
        self.visible_groups = None

    def set_selected_channels(self, keys: set[str] | list[str] | tuple[str, ...] | None) -> None:
        """
        设置当前图表显示哪些通道。

        keys 为 None 表示不按通道过滤。
        例如：
        - {"vin", "vout"}
        - {"iin", "iout"}
        - {"temp"}
        """
        if keys is None:
            self.selected_channels = None
        else:
            self.selected_channels = set(keys)

    def show_channels(self, *keys: str) -> None:
        """
        快速设置当前图表显示的通道。
        """
        self.selected_channels = set(keys)

    def show_all_channels(self) -> None:
        """
        显示所有通道。
        """
        self.selected_channels = None
        self.visible_groups = None

    def pan_time(self, delta_seconds: float) -> None:
        """
        平移时间轴。

        delta_seconds < 0：查看更早的数据
        delta_seconds > 0：查看更靠近当前的数据
        """
        self.time_offset_sec += float(delta_seconds)

        # 不允许拖到未来太多，最多回到实时位置
        if self.time_offset_sec > 0:
            self.time_offset_sec = 0.0

    def reset_time_offset(self) -> None:
        """
        回到实时显示位置。
        """
        self.time_offset_sec = 0.0

    def zoom_time_window(self, factor: float) -> None:
        """
        缩放时基窗口，但不改变当前时间偏移。
        factor < 1：放大，看更短时间
        factor > 1：缩小，看更长时间
        """
        new_window = self.time_window_sec * factor
        new_window = max(1.0, min(new_window, 300.0))
        self.time_window_sec = new_window
