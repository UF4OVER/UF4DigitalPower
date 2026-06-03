# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: channel.py
#  @FileType: 核心基础设施文件，提供设备、数据和通用工具能力
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChannelConfig:
    key: str
    name: str
    unit: str = ""

    min_value: Optional[float] = None
    max_value: Optional[float] = None

    visible: bool = True
    precision: int = 2

    color: Optional[tuple[int, int, int]] = None
    line_width: float = 1.5

    group: str = "default"

    def format_value(self, value: float) -> str:
        return f"{value:.{self.precision}f}{self.unit}"