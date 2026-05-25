# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QLabel
from qfluentwidgets import isDarkTheme

from app.widgets.chart.chart_value_panel import ChartValuePanel
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.chart_control_panel import ChartControlPanel
from app.render.opengl.opengl_chart_widget import OpenGLChartWidget


class RealtimeChartWidget(QWidget):
    """
    实时图表外层控件。

    OpenGL 采用懒初始化：页面构造阶段只创建普通 Qt 控件和占位区，
    主窗口 show 之后进入事件循环，再创建 QOpenGLWidget，避免启动阶段抢占首屏。
    """

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("RealtimeChartWidget")
        self.chart_model = chart_model
        self._opengl_initialized = False

        self._pending_title = "Power Device Realtime Chart"

        self.control_panel = ChartControlPanel(self)
        self.opengl_widget: OpenGLChartWidget | None = None
        self.value_panel = ChartValuePanel(self)

        self.control_panel.groupChanged.connect(self.chart_model.set_visible_groups)
        self.control_panel.groupChanged.connect(lambda *_: self.update_chart())
        self.control_panel.exportRequested.connect(self.export_image_to_file)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.chart_area_layout = QHBoxLayout()
        self.chart_area_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_area_layout.setSpacing(0)

        self.chart_area_layout.addWidget(self.value_panel)

        self.main_layout.addWidget(self.control_panel)
        self.main_layout.addLayout(self.chart_area_layout, 1)

        self.initializeOpenGL()

    def initializeOpenGL(self) -> None:
        """Create QOpenGLWidget after the main window has entered the event loop."""
        if self._opengl_initialized:
            return
        self._opengl_initialized = True

        self.opengl_widget = OpenGLChartWidget(self.chart_model, self)
        self.opengl_widget.set_title(self._pending_title)
        self.opengl_widget.snapshotUpdated.connect(self.value_panel.set_snapshot)

        self.chart_area_layout.insertWidget(0, self.opengl_widget, 1)

        self.refreshTheme()
        self.opengl_widget.update()

    def update_chart(self) -> None:
        if self.opengl_widget is not None:
            self.opengl_widget.update()

    def set_time_window(self, seconds: float) -> None:
        self.chart_model.set_time_window(seconds)
        self.update_chart()

    def set_auto_y_range(self, enabled: bool) -> None:
        self.chart_model.set_auto_y_range(enabled)
        self.update_chart()

    def set_title(self, title: str) -> None:
        self._pending_title = title or "Power Device Realtime Chart"
        if self.opengl_widget is not None:
            self.opengl_widget.set_title(self._pending_title)

    def show_channels(self, *keys: str) -> None:
        self.chart_model.show_channels(*keys)
        self.update_chart()

    def show_all_channels(self) -> None:
        self.chart_model.show_all_channels()
        self.control_panel.setCurrentGroup("all")
        self.update_chart()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        bg = "rgba(18, 22, 30, 0.96)" if dark else "rgba(255, 255, 255, 0.96)"
        border = "rgba(255, 255, 255, 0.08)" if dark else "rgba(15, 23, 42, 0.08)"
        placeholder_bg = "#111827" if dark else "#F8FAFC"
        placeholder_fg = "#94A3B8" if dark else "#64748B"
        self.setStyleSheet(
            f"""
            QWidget#RealtimeChartWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel#ChartOpenGLPlaceholder {{
                background: {placeholder_bg};
                color: {placeholder_fg};
                border-radius: 10px;
                font-size: 13px;
            }}
            """
        )
        self.control_panel.refreshTheme()
        self.value_panel.refreshTheme()
        if self.opengl_widget is not None:
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
        if self.opengl_widget is None:
            self.initializeOpenGL()
        self.repaint()
        pixmap = self.grab()
        pixmap.save(path)
