# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: realtime_chart_widget.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 图表主控件，外部只用它
#  @Python  : 
# -------------------------------

# app/widgets/chart/realtime_chart_widget.py

from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from app.widgets.chart.chart_model import ChartModel
from app.render.opengl.opengl_chart_widget import OpenGLChartWidget


class RealtimeChartWidget(QWidget):
    """
    实时图表外层控件。

    外部页面以后只使用这个类，不直接接触 OpenGLChartWidget。
    """

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)

        self.chart_model = chart_model
        self.opengl_widget = OpenGLChartWidget(chart_model, self)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.opengl_widget.update)
        self.refresh_timer.start(33)  # 约 30FPS

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.opengl_widget)

    def set_time_window(self, seconds: float) -> None:
        self.chart_model.set_time_window(seconds)

    def set_auto_y_range(self, enabled: bool) -> None:
        self.chart_model.set_auto_y_range(enabled)

    def set_title(self, title: str) -> None:
        self.opengl_widget.set_title(title)