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

from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog

from app.widgets.chart.chart_value_panel import ChartValuePanel
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.chart_control_panel import ChartControlPanel

from app.render.opengl.opengl_chart_widget import OpenGLChartWidget



class RealtimeChartWidget(QWidget):
    """
    实时图表外层控件。

    外部页面以后只使用这个类，不直接接触 OpenGLChartWidget。
    """

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)

        self.control_panel = ChartControlPanel(self)
        self.opengl_widget = OpenGLChartWidget(chart_model, self)
        self.value_panel = ChartValuePanel(self)

        # self.control_panel.groupChanged.connect(self.on_group_changed)

        self.control_panel.exportRequested.connect(self.export_image_to_file)

        self.opengl_widget.snapshotUpdated.connect(self.value_panel.set_snapshot)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.opengl_widget.update)
        self.refresh_timer.start(33)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        chart_area_layout = QHBoxLayout()
        chart_area_layout.setContentsMargins(0, 0, 0, 0)
        chart_area_layout.setSpacing(0)

        chart_area_layout.addWidget(self.opengl_widget, 1)
        chart_area_layout.addWidget(self.value_panel)

        main_layout.addWidget(self.control_panel)
        main_layout.addLayout(chart_area_layout, 1)

    def set_time_window(self, seconds: float) -> None:
        self.chart_model.set_time_window(seconds)

    def set_auto_y_range(self, enabled: bool) -> None:
        self.chart_model.set_auto_y_range(enabled)

    def set_title(self, title: str) -> None:
        self.opengl_widget.set_title(title)

    def export_image_to_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出图表图片",
            "chart.png",
            "PNG Image (*.png);;JPEG Image (*.jpg);;Bitmap Image (*.bmp)",
        )

        if not path:
            return

        # 导出整个图表块，包括 OpenGL 区域和右侧数据面板
        self.repaint()
        pixmap = self.grab()
        pixmap.save(path)