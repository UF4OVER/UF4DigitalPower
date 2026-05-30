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
from app.widgets.chart.fallback_chart_widget import FallbackChartWidget
from config import cfg, logger


class RealtimeChartWidget(QWidget):
    """
    实时图表外层控件。

    统一使用 Qt Painter 图表，并将采样输入与界面重绘解耦。
    数据流可以高频写入，界面重绘限制在可控帧率内。
    """

    DEFAULT_RENDER_INTERVAL_MS = 50
    VALUE_PANEL_UPDATE_INTERVAL_MS = 200

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("RealtimeChartWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chart_model = chart_model
        self._chart_initialized = False
        self._pending_title = "Power Device Realtime Chart"
        self._dirty = True
        self._live_updates_suspended = False

        self.control_panel = ChartControlPanel(self)
        self.chart_widget = None
        self.value_panel = ChartValuePanel(self)
        self._pending_panel_snapshot = None

        self._repaint_timer = QTimer(self)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.setInterval(16)
        self._repaint_timer.timeout.connect(self.update_chart)

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(self.DEFAULT_RENDER_INTERVAL_MS)
        self._live_timer.timeout.connect(self._tick_realtime_update)
        self._live_timer.start()

        self._value_panel_timer = QTimer(self)
        self._value_panel_timer.setInterval(self.VALUE_PANEL_UPDATE_INTERVAL_MS)
        self._value_panel_timer.timeout.connect(self._flush_value_panel_snapshot)
        self._value_panel_timer.start()

        try:
            cfg.themeChanged.connect(self.refreshTheme)
        except Exception:
            pass

        self.control_panel.groupChanged.connect(self.chart_model.set_visible_groups)
        self.control_panel.groupChanged.connect(lambda *_: self.request_repaint(data_changed=True))
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

        self.initializeChart()

    def initializeChart(self) -> None:
        """Create the pure Qt chart lazily."""
        if self._chart_initialized:
            return
        self._chart_initialized = True

        self.chart_widget = FallbackChartWidget(self.chart_model, self.chart_area)
        self.chart_widget.set_title(self._pending_title)
        self.chart_widget.snapshotUpdated.connect(self._queue_value_panel_snapshot)
        self.chart_area_layout.insertWidget(0, self.chart_widget, 1)
        logger.info("Using Qt Painter for realtime chart rendering.")

        self.refreshTheme()
        self.mark_data_dirty()
        self.update_chart()

    def _tick_realtime_update(self) -> None:
        if self._live_updates_suspended:
            return
        if self.isVisible() and self.chart_widget is not None and self._dirty:
            self.update_chart()

    def request_repaint(self, data_changed: bool = False) -> None:
        if data_changed:
            self.mark_data_dirty()
        if not self._repaint_timer.isActive():
            self._repaint_timer.start()

    def mark_data_dirty(self) -> None:
        self._dirty = True
        if self.chart_widget is not None:
            self.chart_widget.mark_data_dirty()

    def set_render_fps(self, fps: int) -> None:
        fps = max(1, int(fps))
        self._live_timer.setInterval(max(16, int(1000 / fps)))

    def update_chart(self) -> None:
        if self.chart_widget is not None:
            self.chart_widget.update()
            self._dirty = False

    def _queue_value_panel_snapshot(self, snapshot) -> None:
        self._pending_panel_snapshot = snapshot

    def _flush_value_panel_snapshot(self) -> None:
        if self._live_updates_suspended:
            return
        if self._pending_panel_snapshot is None:
            return
        self.value_panel.set_snapshot(self._pending_panel_snapshot)
        self._pending_panel_snapshot = None

    def set_live_updates_suspended(self, suspended: bool) -> None:
        suspended = bool(suspended)
        if self._live_updates_suspended == suspended:
            return
        self._live_updates_suspended = suspended
        if not suspended:
            self.request_repaint(data_changed=True)
            self._flush_value_panel_snapshot()

    def set_time_window(self, seconds: float) -> None:
        self.chart_model.set_time_window(seconds)
        self.request_repaint(data_changed=True)

    def set_auto_y_range(self, enabled: bool) -> None:
        self.chart_model.set_auto_y_range(enabled)
        self.request_repaint(data_changed=True)

    def set_title(self, title: str) -> None:
        self._pending_title = title or "Power Device Realtime Chart"
        if self.chart_widget is not None:
            self.chart_widget.set_title(self._pending_title)

    def show_channels(self, *keys: str) -> None:
        self.chart_model.show_channels(*keys)
        self.request_repaint(data_changed=True)

    def show_all_channels(self) -> None:
        self.chart_model.show_all_channels()
        self.control_panel.setCurrentGroup("all")
        self.request_repaint(data_changed=True)

    def refreshTheme(self, *_args) -> None:
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
        if self.chart_widget is not None:
            self.chart_widget.refreshTheme()
        if self._pending_panel_snapshot is not None:
            self.value_panel.set_snapshot(self._pending_panel_snapshot)
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
        if self.chart_widget is None:
            self.initializeChart()
        self.repaint()
        pixmap = self.grab()
        pixmap.save(path)
