# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from PyQt5.QtWidgets import QOpenGLWidget, QToolTip
from qfluentwidgets import isDarkTheme

from app.widgets.chart.chart_model import ChartModel, ChartSnapshot
from app.render.opengl.opengl_renderer import OpenGLRenderer


class OpenGLChartWidget(QOpenGLWidget):
    """
    OpenGL 实时曲线控件。

    它只负责显示 ChartModel 生成的 ChartSnapshot，并处理鼠标交互：
    - 左键拖动：时间轴左右平移，只改变 time_offset，不改变时基窗口
    - 滚轮：缩放时基窗口
    - 双击：回到实时位置
    - 悬停：显示最近曲线点的数据类型和数值
    """

    snapshotUpdated = pyqtSignal(object)

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("OpenGLChartWidget")
        self.title = "Power Device Realtime Chart"
        self.chart_model = chart_model
        self.renderer = OpenGLRenderer()
        self.latest_snapshot: ChartSnapshot | None = None

        self._dragging = False
        self._last_drag_x = 0
        self._hover_info: dict | None = None
        self._hover_threshold_px = 12

        self._title_color = QColor(230, 235, 245)
        self._axis_color = QColor(165, 175, 190)
        self._tooltip_bg = QColor(20, 24, 32, 230)
        self._tooltip_fg = QColor(230, 235, 245)
        self._cross_color = QColor(255, 255, 255, 168)
        self._legend_colors = [
            QColor(51, 140, 255),
            QColor(51, 217, 115),
            QColor(255, 166, 51),
            QColor(255, 77, 89),
            QColor(178, 115, 255),
            QColor(51, 217, 217),
            QColor(255, 230, 77),
            QColor(230, 230, 230),
        ]

        self.setMinimumSize(600, 360)
        self.setMouseTracking(True)
        self.refreshTheme()

    def initializeGL(self) -> None:
        self.renderer.initialize()

    def resizeGL(self, width: int, height: int) -> None:
        self.renderer.resize(width, height)

    def paintGL(self) -> None:
        self.latest_snapshot = self.chart_model.build_snapshot()
        self.renderer.render(self.latest_snapshot)
        self._draw_overlay(self.latest_snapshot)
        self.snapshotUpdated.emit(self.latest_snapshot)

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        if dark:
            self._title_color = QColor(245, 247, 250)
            self._axis_color = QColor(165, 175, 190)
            self._tooltip_bg = QColor(20, 24, 32, 232)
            self._tooltip_fg = QColor(235, 240, 248)
            self._cross_color = QColor(255, 255, 255, 168)
        else:
            self._title_color = QColor(17, 24, 39)
            self._axis_color = QColor(71, 85, 105)
            self._tooltip_bg = QColor(255, 255, 255, 236)
            self._tooltip_fg = QColor(15, 23, 42)
            self._cross_color = QColor(15, 23, 42, 118)
        self.update()

    def _draw_overlay(self, snapshot: ChartSnapshot) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        self._draw_title(painter)
        self._draw_axis_info(painter, snapshot)
        self._draw_legend(painter, snapshot)
        self._draw_hover_info(painter)
        painter.end()

    def set_title(self, title: str) -> None:
        self.title = title or "Power Device Realtime Chart"
        self.update()

    def _draw_title(self, painter: QPainter) -> None:
        painter.setPen(self._title_color)
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        painter.drawText(12, 24, self.title)

    def _draw_axis_info(self, painter: QPainter, snapshot: ChartSnapshot) -> None:
        painter.setPen(self._axis_color)
        painter.setFont(QFont("Consolas", 9))
        y_text = f"Y: {snapshot.y_range.minimum:.2f} ~ {snapshot.y_range.maximum:.2f}"
        x_text = f"Window: {snapshot.x_range.span:.1f}s  Offset: {self.chart_model.time_offset_sec:.1f}s"
        painter.drawText(12, self.height() - 28, y_text)
        painter.drawText(12, self.height() - 10, x_text)

    def _draw_legend(self, painter: QPainter, snapshot: ChartSnapshot) -> None:
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
            painter.drawText(
                x,
                y + row * 18,
                f"{curve.name}: {latest_value:.{curve.precision}f}{curve.unit}",
            )
            row += 1

    def _draw_hover_info(self, painter: QPainter) -> None:
        if not self._hover_info:
            return
        x = self._hover_info["px"]
        y = self._hover_info["py"]
        text = self._hover_info["text"]

        pen = QPen(self._cross_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(x, 0, x, self.height())
        painter.drawLine(0, y, self.width(), y)

        painter.setBrush(self._tooltip_fg)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(x - 4, y - 4, 8, 8)

        painter.setFont(QFont("Microsoft YaHei", 9))
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text) + 18
        text_h = 28
        box_x = x + 12
        box_y = y - 36
        if box_x + text_w > self.width():
            box_x = x - text_w - 12
        if box_y < 0:
            box_y = y + 12

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._tooltip_bg)
        painter.drawRoundedRect(box_x, box_y, text_w, text_h, 7, 7)
        painter.setPen(self._tooltip_fg)
        painter.drawText(box_x + 9, box_y + 19, text)

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
        for curve in snapshot.curves:
            for point in curve.points:
                px, py = self._gl_to_pixel(point.gl_x, point.gl_y)
                dx = px - mouse_x
                dy = py - mouse_y
                dist2 = dx * dx + dy * dy
                if dist2 <= best_dist2:
                    best_dist2 = dist2
                    value_text = f"{point.raw_y:.{curve.precision}f}{curve.unit}"
                    best = {
                        "px": px,
                        "py": py,
                        "curve": curve,
                        "point": point,
                        "text": f"{curve.name}: {value_text}",
                    }
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
            self.update()
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
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_info = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        self.chart_model.zoom_time_window(0.8 if delta > 0 else 1.25)
        self.update()
        event.accept()

    def export_image(self, path: str) -> bool:
        if not path:
            return False
        self.repaint()
        pixmap = self.grab()
        return pixmap.save(path)
