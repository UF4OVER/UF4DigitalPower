# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from qfluentwidgets import isDarkTheme

from app.widgets.chart.chart_value_panel import ChartValuePanel
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.chart_control_panel import ChartControlPanel
from app.render.opengl.opengl_chart_widget import OpenGLChartWidget


class RealtimeChartWidget(QWidget):
    """
    实时图表外层控件。

    外部页面只使用这个类：注册 DataHub 后，把实时数据 push 到 DataHub，
    图表内部自动完成通道过滤、鼠标拖动、滚轮时基缩放、悬停数据和图片导出。
    """

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("RealtimeChartWidget")
        self.chart_model = chart_model

        self.control_panel = ChartControlPanel(self)
        self.opengl_widget = OpenGLChartWidget(chart_model, self)
        self.value_panel = ChartValuePanel(self)

        self.control_panel.groupChanged.connect(self.chart_model.set_visible_groups)
        self.control_panel.groupChanged.connect(lambda *_: self.opengl_widget.update())
        self.control_panel.exportRequested.connect(self.export_image_to_file)
        self.opengl_widget.snapshotUpdated.connect(self.value_panel.set_snapshot)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.opengl_widget.update)
        self.refresh_timer.start(33)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        chart_area_layout = QHBoxLayout()
        chart_area_layout.setContentsMargins(0, 0, 0, 0)
        chart_area_layout.setSpacing(0)
        chart_area_layout.addWidget(self.opengl_widget, 1)
        chart_area_layout.addWidget(self.value_panel)

        main_layout.addWidget(self.control_panel)
        main_layout.addLayout(chart_area_layout, 1)

        self.refreshTheme()

    def set_time_window(self, seconds: float) -> None:
        self.chart_model.set_time_window(seconds)
        self.opengl_widget.update()

    def set_auto_y_range(self, enabled: bool) -> None:
        self.chart_model.set_auto_y_range(enabled)
        self.opengl_widget.update()

    def set_title(self, title: str) -> None:
        self.opengl_widget.set_title(title)

    def show_channels(self, *keys: str) -> None:
        self.chart_model.show_channels(*keys)
        self.opengl_widget.update()

    def show_all_channels(self) -> None:
        self.chart_model.show_all_channels()
        self.control_panel.setCurrentGroup("all")
        self.opengl_widget.update()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        bg = "rgba(18, 22, 30, 0.96)" if dark else "rgba(255, 255, 255, 0.96)"
        border = "rgba(255, 255, 255, 0.08)" if dark else "rgba(15, 23, 42, 0.08)"
        self.setStyleSheet(
            f"""
            QWidget#RealtimeChartWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            """
        )
        self.control_panel.refreshTheme()
        self.value_panel.refreshTheme()
        self.opengl_widget.refreshTheme()

    def export_image_to_file(self) -> None:
        default_name = f"power-chart-{time.strftime('%Y%m%d-%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出图表图片",
            str(Path.home() / default_name),
            "PNG Image (*.png);;JPEG Image (*.jpg);;Bitmap Image (*.bmp)",
        )
        if not path:
            return
        self.repaint()
        pixmap = self.grab()
        pixmap.save(path)
