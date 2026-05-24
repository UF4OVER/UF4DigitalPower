# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: channel.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 数据通道
#  @Python  : 
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