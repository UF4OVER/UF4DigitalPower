# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: opengl_renderer.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : OpenGL 曲线渲染主逻辑
#  @Python  :
# -------------------------------
from OpenGL.GL import *

from render.renderer_base import RendererBase
from app.widgets.chart.chart_model import ChartSnapshot, ChartCurve


class OpenGLRenderer(RendererBase):
    """
    OpenGL 图表渲染器。

    背景、网格和中心轴颜色由主题驱动，避免图表内部永远固定为深色。
    """

    def __init__(self):
        self.width = 1
        self.height = 1
        self._dark = True
        self._background = (0.055, 0.060, 0.070, 1.0)
        self._grid = (0.25, 0.28, 0.32, 0.55)
        self._axis = (0.45, 0.48, 0.55, 0.65)
        self.default_colors = [
            (0.20, 0.55, 1.00),
            (0.20, 0.85, 0.45),
            (1.00, 0.65, 0.20),
            (1.00, 0.30, 0.35),
            (0.70, 0.45, 1.00),
            (0.20, 0.85, 0.85),
            (1.00, 0.90, 0.30),
            (0.35, 0.39, 0.45),
        ]
        self.set_theme(True)

    def set_theme(self, dark: bool) -> None:
        self._dark = bool(dark)
        if self._dark:
            self._background = (0.055, 0.060, 0.070, 1.0)
            self._grid = (0.25, 0.28, 0.32, 0.55)
            self._axis = (0.45, 0.48, 0.55, 0.65)
        else:
            self._background = (0.972, 0.980, 0.992, 1.0)
            self._grid = (0.58, 0.64, 0.72, 0.32)
            self._axis = (0.38, 0.45, 0.55, 0.52)

    def initialize(self) -> None:
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        try:
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        except Exception:
            pass

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        glViewport(0, 0, self.width, self.height)

    def render(self, snapshot: ChartSnapshot) -> None:
        glClearColor(*self._background)
        glClear(GL_COLOR_BUFFER_BIT)
        self._draw_grid()
        self._draw_curves(snapshot)
        glFlush()

    def _draw_grid(self) -> None:
        glLineWidth(1.0)
        glColor4f(*self._grid)
        glBegin(GL_LINES)
        for i in range(11):
            x = -1.0 + i * 0.2
            glVertex2f(x, -1.0)
            glVertex2f(x, 1.0)
        for i in range(9):
            y = -1.0 + i * 0.25
            glVertex2f(-1.0, y)
            glVertex2f(1.0, y)
        glEnd()

        glLineWidth(1.2)
        glColor4f(*self._axis)
        glBegin(GL_LINES)
        glVertex2f(-1.0, 0.0)
        glVertex2f(1.0, 0.0)
        glVertex2f(0.0, -1.0)
        glVertex2f(0.0, 1.0)
        glEnd()

    def _draw_curves(self, snapshot: ChartSnapshot) -> None:
        for index, curve in enumerate(snapshot.curves):
            if len(curve.points) < 2:
                continue
            color = self._curve_color(index)
            self._draw_curve(curve, color)

    def _draw_curve(self, curve: ChartCurve, color: tuple[float, float, float]) -> None:
        glLineWidth(1.8)
        glColor4f(color[0], color[1], color[2], 1.0)
        glBegin(GL_LINE_STRIP)
        for point in curve.points:
            glVertex2f(point.gl_x, point.gl_y)
        glEnd()

    def _curve_color(self, index: int) -> tuple[float, float, float]:
        return self.default_colors[index % len(self.default_colors)]
