# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: renderer_base.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 渲染器抽象接口
#  @Python  : 
# -------------------------------
from __future__ import annotations

from abc import ABC, abstractmethod
from app.widgets.chart.chart_model import ChartSnapshot


class RendererBase(ABC):
    """
    图表渲染器基类。

    后面可以同时支持：
    - QPainterRenderer
    - OpenGLRenderer
    """

    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def resize(self, width: int, height: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def render(self, snapshot: ChartSnapshot) -> None:
        raise NotImplementedError