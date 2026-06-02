# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: fallback_chart_widget.py
#  @FileType: 图表组件文件，负责实时曲线、图表模型和数据展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

import bisect

from PyQt5.QtCore import QEvent, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import ToolTip, isDarkTheme

from app.widgets.chart.chart_model import ChartModel, ChartSnapshot


class ChartHoverToolTip(ToolTip):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        font = QFont(parent.font() if parent is not None else self.font())
        font.setPointSize(9)
        self.label.setFont(font)
        self.label.setWordWrap(False)
        self.setDuration(-1)


class FallbackChartWidget(QWidget):
    """Pure Qt realtime chart with capped repaint and cached draw paths."""

    snapshotUpdated = pyqtSignal(object)

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("FallbackChartWidget")
        self.chart_model = chart_model
        self.title = "Power Device Realtime Chart"
        self.latest_snapshot: ChartSnapshot | None = None
        self._dragging = False
        self._last_drag_x = 0
        self._hover_info: dict | None = None
        self._hover_threshold_px = 12
        self._snapshot_dirty = True
        self._cached_paths: list[QPainterPath] = []
        self._cached_size: tuple[int, int] = (0, 0)
        self._interaction_dirty = False
        self._interaction_timer = None
        self._hover_tooltip: ToolTip | None = None
        self._legend_colors = [
            QColor(51, 140, 255), QColor(51, 217, 115), QColor(255, 166, 51),
            QColor(255, 77, 89), QColor(178, 115, 255), QColor(51, 217, 217),
            QColor(255, 230, 77), QColor(75, 85, 99),
        ]
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(600, 360)
        self.setMouseTracking(True)
        self.refreshTheme()
        self._initInteractionTimer()

    def _initInteractionTimer(self) -> None:
        from PyQt5.QtCore import QTimer

        self._interaction_timer = QTimer(self)
        self._interaction_timer.setSingleShot(True)
        self._interaction_timer.setInterval(16)
        self._interaction_timer.timeout.connect(self._flush_interaction_update)

    def set_title(self, title: str) -> None:
        self.title = title or "Power Device Realtime Chart"
        self.update()

    def mark_data_dirty(self) -> None:
        self._snapshot_dirty = True

    def _schedule_interaction_update(self, data_changed: bool = False) -> None:
        if data_changed:
            self._snapshot_dirty = True
        self._interaction_dirty = True
        if self._interaction_timer is not None and not self._interaction_timer.isActive():
            self._interaction_timer.start()

    def _flush_interaction_update(self) -> None:
        if not self._interaction_dirty:
            return
        self._interaction_dirty = False
        self.update()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        if dark:
            self._title_color = QColor(245, 247, 250)
            self._axis_color = QColor(165, 175, 190)
            self._grid_color = QColor(148, 163, 184, 58)
            self._cross_color = QColor(255, 255, 255, 168)
        else:
            self._title_color = QColor(17, 24, 39)
            self._axis_color = QColor(71, 85, 105)
            self._grid_color = QColor(51, 65, 85, 62)
            self._cross_color = QColor(15, 23, 42, 118)
        self.setStyleSheet("""
            QWidget#FallbackChartWidget {
                background: transparent;
                border: none;
            }
        """)
        self.update()

    def paintEvent(self, event) -> None:
        self._ensure_snapshot()
        if self.latest_snapshot is None:
            return
        painter = QPainter(self)
        total_points = sum(len(curve.points) for curve in self.latest_snapshot.curves)
        painter.setRenderHint(QPainter.Antialiasing, total_points <= 2500)
        painter.setRenderHint(QPainter.TextAntialiasing)
        self._draw_grid(painter)
        self._draw_curves(painter, self.latest_snapshot)
        self._draw_overlay(painter, self.latest_snapshot)
        painter.end()

    def resizeEvent(self, event) -> None:
        self.mark_data_dirty()
        super().resizeEvent(event)

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            return True
        return super().event(event)

    def _ensure_snapshot(self) -> None:
        size = (self.width(), self.height())
        if not self._snapshot_dirty and self.latest_snapshot is not None and size == self._cached_size:
            return

        self._cached_size = size
        self.latest_snapshot = self.chart_model.build_snapshot_for_width(max(1, self.width()))
        self._cached_paths = self._build_paths(self.latest_snapshot)
        self._snapshot_dirty = False
        self.snapshotUpdated.emit(self.latest_snapshot)

    def _build_paths(self, snapshot: ChartSnapshot) -> list[QPainterPath]:
        paths: list[QPainterPath] = []
        for curve in snapshot.curves:
            path = QPainterPath()
            if curve.points:
                first = curve.points[0]
                path.moveTo(*self._gl_to_pixel(first.gl_x, first.gl_y))
                for point in curve.points[1:]:
                    path.lineTo(*self._gl_to_pixel(point.gl_x, point.gl_y))
            paths.append(path)
        return paths

    def _draw_grid(self, painter: QPainter) -> None:
        painter.setPen(QPen(self._grid_color, 1))
        w = max(1, self.width())
        h = max(1, self.height())
        for i in range(11):
            x = round(i * w / 10)
            painter.drawLine(x, 0, x, h)
        for i in range(9):
            y = round(i * h / 8)
            painter.drawLine(0, y, w, y)
        painter.setPen(QPen(self._axis_color, 1))
        painter.drawLine(0, h // 2, w, h // 2)
        painter.drawLine(w // 2, 0, w // 2, h)

    def _draw_curves(self, painter: QPainter, snapshot: ChartSnapshot) -> None:
        for index, curve in enumerate(snapshot.curves):
            if len(curve.points) < 2:
                continue
            color = self._legend_colors[index % len(self._legend_colors)]
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            if index < len(self._cached_paths):
                painter.drawPath(self._cached_paths[index])

    def _draw_overlay(self, painter: QPainter, snapshot: ChartSnapshot) -> None:
        painter.setPen(self._title_color)
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        painter.drawText(12, 24, self.title + "  (Qt)")

        painter.setPen(self._axis_color)
        painter.setFont(QFont("Consolas", 9))
        y_text = f"Y: {snapshot.y_range.minimum:.2f} ~ {snapshot.y_range.maximum:.2f}"
        x_text = f"Window: {snapshot.x_range.span:.1f}s  Offset: {self.chart_model.time_offset_sec:.1f}s"
        painter.drawText(12, self.height() - 28, y_text)
        painter.drawText(12, self.height() - 10, x_text)

        x = max(12, self.width() - 190)
        y = 20
        painter.setFont(QFont("Microsoft YaHei", 9))
        row = 0
        for index, curve in enumerate(snapshot.curves):
            if not curve.points:
                continue
            color = self._legend_colors[index % len(self._legend_colors)]
            latest_value = curve.points[-1].raw_y
            painter.setPen(color)
            painter.drawText(x, y + row * 18, f"{curve.name}: {latest_value:.{curve.precision}f}{curve.unit}")
            row += 1

        self._draw_hover_info(painter)

    def _draw_hover_info(self, painter: QPainter) -> None:
        if not self._hover_info:
            self._hide_hover_tooltip()
            return
        x = self._hover_info["px"]
        y = self._hover_info["py"]
        painter.setPen(QPen(self._cross_color, 1))
        painter.drawLine(x, 0, x, self.height())
        painter.drawLine(0, y, self.width(), y)
        dot_color = self._title_color if isDarkTheme() else self._axis_color
        painter.setBrush(dot_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(x - 4, y - 4, 8, 8)
        self._sync_hover_tooltip()

    def _ensure_hover_tooltip(self) -> ToolTip:
        if self._hover_tooltip is None:
            self._hover_tooltip = ChartHoverToolTip("", self.window())
        return self._hover_tooltip

    def _hide_hover_tooltip(self) -> None:
        if self._hover_tooltip is not None:
            self._hover_tooltip.hide()

    def _sync_hover_tooltip(self) -> None:
        if not self._hover_info:
            self._hide_hover_tooltip()
            return

        text = self._hover_info["text"]
        px = self._hover_info["px"]
        py = self._hover_info["py"]
        tooltip = self._ensure_hover_tooltip()
        tooltip.setText(text)
        tooltip.adjustSize()

        x = px + 12
        y = py - tooltip.height() - 12
        if x + tooltip.width() > self.width() - 8:
            x = px - tooltip.width() - 12
        if y < 8:
            y = py + 12

        global_pos = self.mapToGlobal(QPoint(max(8, x), max(8, y)))
        tooltip.move(global_pos)
        tooltip.show()
        tooltip.raise_()

    def _gl_to_pixel(self, gl_x: float, gl_y: float) -> tuple[int, int]:
        px = int((gl_x + 1.0) * 0.5 * self.width())
        py = int((1.0 - (gl_y + 1.0) * 0.5) * self.height())
        return px, py

    def _update_hover_info(self, mouse_x: int, mouse_y: int) -> None:
        snapshot = self.latest_snapshot
        if snapshot is None:
            self._hover_info = None
            return
        best = None
        best_dist2 = self._hover_threshold_px * self._hover_threshold_px
        target_time = self.chart_model.pixel_to_time(mouse_x, max(1, self.width()), snapshot.x_range)
        for curve in snapshot.curves:
            if not curve.points:
                continue
            times = [point.raw_x for point in curve.points]
            insert_at = bisect.bisect_left(times, target_time)
            candidate_indexes = range(max(0, insert_at - 2), min(len(curve.points), insert_at + 3))
            for index in candidate_indexes:
                point = curve.points[index]
                px, py = self._gl_to_pixel(point.gl_x, point.gl_y)
                dx = px - mouse_x
                dy = py - mouse_y
                dist2 = dx * dx + dy * dy
                if dist2 <= best_dist2:
                    best_dist2 = dist2
                    value_text = f"{point.raw_y:.{curve.precision}f}{curve.unit}"
                    best = {"px": px, "py": py, "text": f"{curve.name}: {value_text}"}
        self._hover_info = best

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_drag_x = event.pos().x()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.pos()
        if self._dragging:
            dx = pos.x() - self._last_drag_x
            self._last_drag_x = pos.x()
            seconds_per_px = self.chart_model.time_window_sec / max(1, self.width())
            self.chart_model.pan_time(-dx * seconds_per_px)
            self._hover_info = None
            self._hide_hover_tooltip()
            self._schedule_interaction_update(data_changed=True)
            event.accept()
            return
        self._update_hover_info(pos.x(), pos.y())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.chart_model.reset_time_offset()
            self._schedule_interaction_update(data_changed=True)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_info = None
        self._hide_hover_tooltip()
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        self.chart_model.zoom_time_window(0.8 if delta > 0 else 1.25)
        self._schedule_interaction_update(data_changed=True)
        event.accept()
