# -*- coding: utf-8 -*-
"""Lightweight Qt-only plotting shim used by F4CP.

This module intentionally implements only the small subset of the pyqtgraph API
used by ``app.pages.page_power``. It avoids numpy and external plotting
backends, which keeps the frozen package smaller and prevents pyqtgraph from
pulling numpy back into the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QFrame


def mkPen(color=None, width: int = 1, style=Qt.SolidLine):
    if isinstance(color, QPen):
        pen = QPen(color)
    elif color is None:
        pen = QPen(QColor("#3B82F6"))
    else:
        pen = QPen(QColor(color))
    pen.setWidth(max(1, int(width)))
    pen.setStyle(style)
    pen.setCosmetic(True)
    return pen


class _AxisItem:
    def __init__(self, owner: "PlotWidget", name: str):
        self._owner = owner
        self._name = name
        self._label = ""
        self._units = ""
        self._text_pen = QPen(QColor("#334155"))
        self._pen = QPen(QColor("#334155"))
        self._grid_alpha = 0

    def setTextPen(self, pen):
        self._text_pen = mkPen(pen) if not isinstance(pen, QPen) else QPen(pen)
        self._owner.update()

    def setPen(self, pen):
        self._pen = mkPen(pen) if not isinstance(pen, QPen) else QPen(pen)
        self._owner.update()

    def setLabel(self, text: str, color=None, units: str | None = None):
        self._label = str(text or "")
        self._units = str(units or "")
        if color is not None:
            self.setTextPen(mkPen(color))
        self._owner.update()

    def setTickPen(self, pen):
        self.setPen(pen)

    def setStyle(self, **_kwargs):
        self._owner.update()

    def setGrid(self, alpha: int):
        self._grid_alpha = int(alpha or 0)
        self._owner.update()


class _ViewBox:
    def __init__(self, owner: "PlotWidget"):
        self._owner = owner
        self._border_pen = QPen(QColor(0, 0, 0, 0))

    def setMouseEnabled(self, x: bool = True, y: bool = True):
        self._owner._mouse_x = bool(x)
        self._owner._mouse_y = bool(y)

    def setMenuEnabled(self, _enabled: bool):
        pass

    def setBorder(self, pen):
        self._border_pen = pen if isinstance(pen, QPen) else mkPen(pen)
        self._owner.update()


class _PlotItem:
    def __init__(self, owner: "PlotWidget"):
        self._owner = owner
        self._axes = {
            "left": _AxisItem(owner, "left"),
            "bottom": _AxisItem(owner, "bottom"),
        }
        self._view_box = _ViewBox(owner)

    def hideButtons(self):
        pass

    def getAxis(self, name: str) -> _AxisItem:
        return self._axes[name]

    def getViewBox(self) -> _ViewBox:
        return self._view_box

    def setTitle(self, _title: str):
        pass

    def showGrid(self, x: bool = True, y: bool = True, alpha: float = 0.2):
        self._owner.showGrid(x=x, y=y, alpha=alpha)


class _Legend:
    def __init__(self, owner: "PlotWidget"):
        self._owner = owner
        self._brush = QColor(255, 255, 255, 220)
        self._pen = QPen(QColor(0, 0, 0, 30))
        self._text_color = QColor("#334155")
        self._text_size = 9

    def setBrush(self, brush):
        self._brush = QColor(brush)
        self._owner.update()

    def setPen(self, pen):
        self._pen = pen if isinstance(pen, QPen) else mkPen(pen)
        self._owner.update()

    def setLabelTextColor(self, color):
        self._text_color = QColor(color)
        self._owner.update()

    def setLabelTextSize(self, size: str):
        try:
            self._text_size = int(str(size).replace("pt", "").strip())
        except ValueError:
            self._text_size = 9
        self._owner.update()


@dataclass
class _Curve:
    name: str
    pen: QPen
    x: list[float]
    y: list[float]

    def setClipToView(self, _enabled: bool):
        pass

    def setPen(self, pen):
        self.pen = pen if isinstance(pen, QPen) else mkPen(pen)

    def setData(self, x_values: Iterable[float], y_values: Iterable[float]):
        self.x = [float(v) for v in x_values]
        self.y = [float(v) for v in y_values]


class PlotWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot_item = _PlotItem(self)
        self._view_box = self._plot_item.getViewBox()
        self._curves: list[_Curve] = []
        self._legend: _Legend | None = None
        self._x_range = (0.0, 240.0)
        self._y_range = (0.0, 45.0)
        self._grid_x = True
        self._grid_y = True
        self._grid_alpha = 0.18
        self._antialias = True
        self._background = QColor(0, 0, 0, 0)
        self._mouse_x = False
        self._mouse_y = False
        self.setMinimumHeight(260)

    def setYRange(self, minimum: float, maximum: float, padding: float = 0):
        self._y_range = (float(minimum), float(maximum))
        self.update()

    def setXRange(self, minimum: float, maximum: float, padding: float = 0):
        self._x_range = (float(minimum), float(maximum))
        self.update()

    def addLegend(self, offset=(12, 12)):
        self._legend = _Legend(self)
        return self._legend

    def plot(self, name: str = "", pen=None):
        curve = _Curve(str(name or ""), pen if isinstance(pen, QPen) else mkPen(pen), [], [])
        self._curves.append(curve)
        self.update()
        return _CurveAdapter(self, curve)

    def setMouseEnabled(self, x: bool = True, y: bool = True):
        self._mouse_x = bool(x)
        self._mouse_y = bool(y)

    def showGrid(self, x: bool = True, y: bool = True, alpha: float = 0.18):
        self._grid_x = bool(x)
        self._grid_y = bool(y)
        self._grid_alpha = float(alpha)
        self.update()

    def setAntialiasing(self, enabled: bool):
        self._antialias = bool(enabled)
        self.update()

    def setMenuEnabled(self, _enabled: bool):
        pass

    def getPlotItem(self) -> _PlotItem:
        return self._plot_item

    def getViewBox(self) -> _ViewBox:
        return self._view_box

    def enableAutoRange(self, x: bool = False, y: bool = False):
        pass

    def setBackground(self, color):
        if isinstance(color, tuple):
            self._background = QColor(*color)
        else:
            self._background = QColor(color)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self._antialias:
            painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(48, 16, -16, -36)
        if rect.width() <= 4 or rect.height() <= 4:
            return

        painter.fillRect(self.rect(), self._background)
        self._draw_grid(painter, rect)
        self._draw_axes(painter, rect)
        self._draw_curves(painter, rect)
        self._draw_legend(painter, rect)

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        grid_color = QColor(128, 128, 128, max(12, min(96, int(self._grid_alpha * 255))))
        painter.setPen(QPen(grid_color, 1, Qt.DotLine))
        if self._grid_y:
            for index in range(1, 5):
                y = rect.top() + rect.height() * index / 5.0
                painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        if self._grid_x:
            for index in range(1, 6):
                x = rect.left() + rect.width() * index / 6.0
                painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))

    def _draw_axes(self, painter: QPainter, rect: QRectF) -> None:
        axis = self._plot_item.getAxis("left")
        painter.setPen(axis._pen)
        painter.drawRect(rect)
        painter.setPen(axis._text_pen)
        y_min, y_max = self._y_range
        for index in range(0, 6):
            ratio = index / 5.0
            value = y_max - (y_max - y_min) * ratio
            y = rect.top() + rect.height() * ratio
            painter.drawText(4, int(y - 8), 40, 16, Qt.AlignRight | Qt.AlignVCenter, f"{value:g}")
        bottom = self._plot_item.getAxis("bottom")
        label = bottom._label or "采样点"
        painter.drawText(rect.left(), rect.bottom() + 8, rect.width(), 20, Qt.AlignCenter, label)
        ylabel = axis._label + ((" / " + axis._units) if axis._units else "")
        painter.drawText(4, 2, int(rect.width()), 18, Qt.AlignLeft | Qt.AlignVCenter, ylabel)

    def _draw_curves(self, painter: QPainter, rect: QRectF) -> None:
        x_min, x_max = self._x_range
        y_min, y_max = self._y_range
        if x_max <= x_min:
            x_max = x_min + 1.0
        if y_max <= y_min:
            y_max = y_min + 1.0

        for curve in self._curves:
            if len(curve.x) < 2 or len(curve.y) < 2:
                continue
            painter.setPen(curve.pen)
            path = QPainterPath()
            first = True
            for x_val, y_val in zip(curve.x, curve.y):
                px = rect.left() + (x_val - x_min) / (x_max - x_min) * rect.width()
                py = rect.bottom() - (y_val - y_min) / (y_max - y_min) * rect.height()
                point = QPointF(px, py)
                if first:
                    path.moveTo(point)
                    first = False
                else:
                    path.lineTo(point)
            painter.drawPath(path)

    def _draw_legend(self, painter: QPainter, rect: QRectF) -> None:
        if self._legend is None or not self._curves:
            return
        painter.save()
        painter.setFont(painter.font())
        fm = QFontMetrics(painter.font())
        entries = [curve for curve in self._curves if curve.name]
        width = max((fm.horizontalAdvance(curve.name) for curve in entries), default=20) + 42
        height = max(22, len(entries) * 20 + 8)
        box = QRectF(rect.left() + 10, rect.top() + 10, width, height)
        painter.setBrush(self._legend._brush)
        painter.setPen(self._legend._pen)
        painter.drawRoundedRect(box, 6, 6)
        painter.setPen(self._legend._text_color)
        for index, curve in enumerate(entries):
            y = box.top() + 14 + index * 20
            painter.setPen(curve.pen)
            painter.drawLine(int(box.left() + 8), int(y), int(box.left() + 26), int(y))
            painter.setPen(self._legend._text_color)
            painter.drawText(int(box.left() + 32), int(y - 8), int(width - 36), 16, Qt.AlignLeft | Qt.AlignVCenter, curve.name)
        painter.restore()


class _CurveAdapter:
    def __init__(self, owner: PlotWidget, curve: _Curve):
        self._owner = owner
        self._curve = curve

    def setClipToView(self, enabled: bool):
        self._curve.setClipToView(enabled)

    def setPen(self, pen):
        self._curve.setPen(pen)
        self._owner.update()

    def setData(self, x_values: Iterable[float], y_values: Iterable[float]):
        self._curve.setData(x_values, y_values)
        self._owner.update()
