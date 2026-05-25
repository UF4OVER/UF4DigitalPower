# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from qfluentwidgets import isDarkTheme

from app.widgets.chart.chart_value_panel import ChartValuePanel
from app.widgets.chart.chart_model import ChartModel
from app.widgets.chart.chart_control_panel import ChartControlPanel
from app.render.opengl.opengl_chart_widget import OpenGLChartWidget


class RealtimeChartWidget(QWidget):
    """
    实时图表外层控件。

    - 外层圆角、半透明卡片
    - OpenGL 图表区域背景透明
    - 数据进入后使用短间隔刷新节流，保证实时性同时避免过度重绘
    """

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("RealtimeChartWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chart_model = chart_model
        self._opengl_initialized = False
        self._pending_title = "Power Device Realtime Chart"
        self._last_paint_request_ms = 0

        self.control_panel = ChartControlPanel(self)
        self.opengl_widget: OpenGLChartWidget | None = None
        self.value_panel = ChartValuePanel(self)

        self._repaint_timer = QTimer(self)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.setInterval(16)
        self._repaint_timer.timeout.connect(self.update_chart)

        self.control_panel.groupChanged.connect(self.chart_model.set_visible_groups)
        self.control_panel.groupChanged.connect(lambda *_: self.request_repaint())
        self.control_panel.exportRequested.connect(self.export_image_to_file)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)

        self.chart_area = QWidget(self)
        self.chart_area.setObjectName("ChartTransparentArea")
        self.chart_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chart_area_layout = QHBoxLayout(self.chart_area)
        self.chart_area_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_area_layout.setSpacing(10)
        self.chart_area_layout.addWidget(self.value_panel)

        self.main_layout.addWidget(self.control_panel)
        self.main_layout.addWidget(self.chart_area, 1)

        self.initializeOpenGL()

    def initializeOpenGL(self) -> None:
        """Create QOpenGLWidget after the main window has entered the event loop."""
        if self._opengl_initialized:
            return
        self._opengl_initialized = True

        self.opengl_widget = OpenGLChartWidget(self.chart_model, self.chart_area)
        self.opengl_widget.set_title(self._pending_title)
        self.opengl_widget.snapshotUpdated.connect(self.value_panel.set_snapshot)

        self.chart_area_layout.insertWidget(0, self.opengl_widget, 1)

        self.refreshTheme()
        self.opengl_widget.update()

    def request_repaint(self) -> None:
        """Request one chart repaint with a small throttle for realtime streams."""
        if not self._repaint_timer.isActive():
            self._repaint_timer.start()

    def update_chart(self) -> None:
        if self.opengl_widget is not None:
            self.opengl_widget.update()

    def set_time_window(self, seconds: float) -> None:
        self.chart_model.set_time_window(seconds)
        self.request_repaint()

    def set_auto_y_range(self, enabled: bool) -> None:
        self.chart_model.set_auto_y_range(enabled)
        self.request_repaint()

    def set_title(self, title: str) -> None:
        self._pending_title = title or "Power Device Realtime Chart"
        if self.opengl_widget is not None:
            self.opengl_widget.set_title(self._pending_title)

    def show_channels(self, *keys: str) -> None:
        self.chart_model.show_channels(*keys)
        self.request_repaint()

    def show_all_channels(self) -> None:
        self.chart_model.show_all_channels()
        self.control_panel.setCurrentGroup("all")
        self.request_repaint()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        card_bg = "rgba(255, 255, 255, 0.045)" if dark else "rgba(255, 255, 255, 0.54)"
        border = "rgba(255, 255, 255, 0.10)" if dark else "rgba(15, 23, 42, 0.08)"
        area_bg = "rgba(255, 255, 255, 0.020)" if dark else "rgba(255, 255, 255, 0.20)"
        self.setStyleSheet(
            f"""
            QWidget#RealtimeChartWidget {{
                background: {card_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QWidget#ChartTransparentArea {{
                background: {area_bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            """
        )
        self.control_panel.refreshTheme()
        self.value_panel.refreshTheme()
        if self.opengl_widget is not None:
            self.opengl_widget.refreshTheme()
        self.request_repaint()

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
