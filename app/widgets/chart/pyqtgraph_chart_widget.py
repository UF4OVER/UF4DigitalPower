# -*- coding: utf-8 -*-
from __future__ import annotations

import bisect

import pyqtgraph as pg
from PyQt5.QtCore import QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import isDarkTheme

from app.widgets.chart.chart_model import ChartModel, ChartSnapshot


class _InteractivePlotWidget(pg.PlotWidget):
    def __init__(self, owner: "PyQtGraphChartWidget", parent=None):
        super().__init__(parent)
        self._owner = owner

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._owner._beginDrag(event.pos().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._owner._dragging:
            self._owner._dragTo(event.pos().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._owner._dragging:
            self._owner._endDrag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._owner._resetTimeOffset()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:
        self._owner._zoomTime(event.angleDelta().y())
        event.accept()

    def leaveEvent(self, event) -> None:
        self._owner._setHoverVisible(False)
        super().leaveEvent(event)


class PyQtGraphChartWidget(QWidget):
    """PyQtGraph realtime chart with the same interaction contract as the old chart."""

    snapshotUpdated = pyqtSignal(object)

    def __init__(self, chart_model: ChartModel, parent=None):
        super().__init__(parent)
        self.setObjectName("PyQtGraphChartWidget")
        self.chart_model = chart_model
        self.title = "Power Device Realtime Chart"
        self.latest_snapshot: ChartSnapshot | None = None
        self._snapshot_dirty = True
        self._dragging = False
        self._last_drag_x = 0
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._hover_threshold_px = 12

        self.plot = _InteractivePlotWidget(self, self)
        self.plot.setMouseTracking(True)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.28)
        self.plot.setLabel("bottom", "时间", units="s")
        self.plot.setLabel("left", "值")
        self.plot.addLegend(offset=(10, 10))
        self.plot.scene().sigMouseMoved.connect(self._onMouseMoved)

        self._vline = pg.InfiniteLine(angle=90, movable=False)
        self._hline = pg.InfiniteLine(angle=0, movable=False)
        self._hover_dot = pg.ScatterPlotItem(size=9)
        self._hover_text = pg.TextItem("", anchor=(0, 1))
        for item in (self._vline, self._hline, self._hover_dot, self._hover_text):
            self.plot.addItem(item, ignoreBounds=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        self.setMinimumSize(600, 360)
        self.refreshTheme()
        self._setHoverVisible(False)

    def set_title(self, title: str) -> None:
        self.title = title or "Power Device Realtime Chart"
        self.plot.setTitle(self.title + "  (PyQtGraph)")

    def mark_data_dirty(self) -> None:
        self._snapshot_dirty = True

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        if dark:
            background = QColor("#313131")
            foreground = QColor(226, 232, 240)
            grid = QColor(148, 163, 184, 70)
            hover = QColor(255, 255, 255, 150)
        else:
            background = QColor("#fdfdfd")
            foreground = QColor(15, 23, 42)
            grid = QColor(51, 65, 85, 60)
            hover = QColor(15, 23, 42, 120)

        self.plot.setBackground(background)
        self.plot.setTitle(self.title + "  (PyQtGraph)", color=foreground.name(), size="10pt")
        self.plot.getAxis("bottom").setPen(foreground)
        self.plot.getAxis("left").setPen(foreground)
        self.plot.getAxis("bottom").setTextPen(foreground)
        self.plot.getAxis("left").setTextPen(foreground)
        self.plot.getAxis("bottom").setStyle(tickFont=QFont("Consolas", 8))
        self.plot.getAxis("left").setStyle(tickFont=QFont("Consolas", 8))
        self.plot.getPlotItem().ctrl.xGridCheck.setChecked(True)
        self.plot.getPlotItem().ctrl.yGridCheck.setChecked(True)
        self.plot.showGrid(x=True, y=True, alpha=0.28)
        self._vline.setPen(pg.mkPen(hover, width=1))
        self._hline.setPen(pg.mkPen(hover, width=1))
        self.setStyleSheet("QWidget#PyQtGraphChartWidget { background: transparent; border: none; }")

        # PyQtGraph uses its own grid pens internally; a repaint is enough after theme changes.
        self.update_plot(force=True)

    def update(self, *args, **kwargs) -> None:
        self.update_plot()
        super().update(*args, **kwargs)

    def update_plot(self, force: bool = False) -> None:
        if not force and not self._snapshot_dirty and self.latest_snapshot is not None:
            return

        snapshot = self.chart_model.build_snapshot_for_width(max(1, self.plot.width()))
        self.latest_snapshot = snapshot
        self._snapshot_dirty = False
        self._sync_curves(snapshot)
        self._apply_ranges(snapshot)
        self.snapshotUpdated.emit(snapshot)

    def _sync_curves(self, snapshot: ChartSnapshot) -> None:
        active_keys: set[str] = set()
        for index, curve in enumerate(snapshot.curves):
            active_keys.add(curve.key)
            item = self._curves.get(curve.key)
            if item is None:
                color = self._curveColor(curve, index)
                item = self.plot.plot(
                    [],
                    [],
                    pen=pg.mkPen(color, width=max(1.0, self._lineWidth(curve.key))),
                    name=f"{curve.name} ({curve.unit})" if curve.unit else curve.name,
                )
                self._curves[curve.key] = item

            x_values = [point.raw_x - snapshot.x_range.maximum for point in curve.points]
            y_values = [point.raw_y for point in curve.points]
            item.setData(x_values, y_values)

        for key in list(self._curves):
            if key not in active_keys:
                self.plot.removeItem(self._curves.pop(key))

    def _apply_ranges(self, snapshot: ChartSnapshot) -> None:
        self.plot.setXRange(-snapshot.x_range.span, 0.0, padding=0.0)
        self.plot.setYRange(snapshot.y_range.minimum, snapshot.y_range.maximum, padding=0.02)

    def _curveColor(self, curve, index: int) -> QColor:
        channel = self.chart_model.data_hub.get_channel(curve.key)
        if channel is not None and channel.config.color:
            return QColor(*channel.config.color)
        palette = (
            QColor(51, 140, 255), QColor(51, 217, 115), QColor(255, 166, 51),
            QColor(255, 77, 89), QColor(178, 115, 255), QColor(51, 217, 217),
            QColor(255, 230, 77), QColor(75, 85, 99),
        )
        return palette[index % len(palette)]

    def _lineWidth(self, key: str) -> float:
        channel = self.chart_model.data_hub.get_channel(key)
        if channel is None:
            return 2.0
        return channel.config.line_width

    def _beginDrag(self, x: int) -> None:
        self._dragging = True
        self._last_drag_x = int(x)
        self.plot.setCursor(Qt.ClosedHandCursor)
        self._setHoverVisible(False)

    def _dragTo(self, x: int) -> None:
        dx = int(x) - self._last_drag_x
        self._last_drag_x = int(x)
        seconds_per_px = self.chart_model.time_window_sec / max(1, self.plot.width())
        self.chart_model.pan_time(-dx * seconds_per_px)
        self.mark_data_dirty()
        self.update_plot()
        self._setHoverVisible(False)

    def _endDrag(self) -> None:
        self._dragging = False
        self.plot.setCursor(Qt.ArrowCursor)

    def _resetTimeOffset(self) -> None:
        self.chart_model.reset_time_offset()
        self.mark_data_dirty()
        self.update_plot()

    def _zoomTime(self, wheel_delta: int) -> None:
        self.chart_model.zoom_time_window(0.8 if wheel_delta > 0 else 1.25)
        self.mark_data_dirty()
        self.update_plot()

    def _onMouseMoved(self, scene_pos) -> None:
        if self._dragging or self.latest_snapshot is None:
            return
        if not self.plot.sceneBoundingRect().contains(scene_pos):
            self._setHoverVisible(False)
            return
        view_pos = self.plot.getPlotItem().vb.mapSceneToView(scene_pos)
        self._updateHover(view_pos.x(), view_pos.y(), scene_pos)

    def _updateHover(self, x_value: float, y_value: float, scene_pos) -> None:
        snapshot = self.latest_snapshot
        if snapshot is None:
            self._setHoverVisible(False)
            return

        target_time = snapshot.x_range.maximum + x_value
        best = None
        best_dist2 = self._hover_threshold_px * self._hover_threshold_px
        for curve in snapshot.curves:
            if not curve.points:
                continue
            times = [point.raw_x for point in curve.points]
            insert_at = bisect.bisect_left(times, target_time)
            candidate_indexes = range(max(0, insert_at - 2), min(len(curve.points), insert_at + 3))
            for index in candidate_indexes:
                point = curve.points[index]
                point_x = point.raw_x - snapshot.x_range.maximum
                point_y = point.raw_y
                point_scene = self.plot.getPlotItem().vb.mapViewToScene(pg.Point(point_x, point_y))
                dx = point_scene.x() - scene_pos.x()
                dy = point_scene.y() - scene_pos.y()
                dist2 = dx * dx + dy * dy
                if dist2 <= best_dist2:
                    best_dist2 = dist2
                    best = (curve, point_x, point_y)

        if best is None:
            self._setHoverVisible(False)
            return

        curve, point_x, point_y = best
        self._vline.setPos(point_x)
        self._hline.setPos(point_y)
        self._hover_dot.setData([point_x], [point_y])
        self._hover_text.setText(f"{curve.name}: {point_y:.{curve.precision}f}{curve.unit}")
        self._hover_text.setPos(point_x, point_y)
        self._setHoverVisible(True)

    def _setHoverVisible(self, visible: bool) -> None:
        self._vline.setVisible(visible)
        self._hline.setVisible(visible)
        self._hover_dot.setVisible(visible)
        self._hover_text.setVisible(visible)
