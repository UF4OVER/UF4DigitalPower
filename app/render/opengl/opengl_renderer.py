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
    OpenGL 图表渲染器第一版。

    当前版本先使用 glBegin/glEnd 打通流程。
    后面再升级为 VBO + Shader。
    """

    def __init__(self):
        self.width = 1
        self.height = 1

        self.default_colors = [
            (0.20, 0.55, 1.00),
            (0.20, 0.85, 0.45),
            (1.00, 0.65, 0.20),
            (1.00, 0.30, 0.35),
            (0.70, 0.45, 1.00),
            (0.20, 0.85, 0.85),
            (1.00, 0.90, 0.30),
            (0.90, 0.90, 0.90),
        ]

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
        glClearColor(0.055, 0.060, 0.070, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        self._draw_grid()
        self._draw_curves(snapshot)

        glFlush()

    def _draw_grid(self) -> None:
        glLineWidth(1.0)
        glColor4f(0.25, 0.28, 0.32, 0.55)

        glBegin(GL_LINES)

        # 竖向网格
        for i in range(11):
            x = -1.0 + i * 0.2
            glVertex2f(x, -1.0)
            glVertex2f(x, 1.0)

        # 横向网格
        for i in range(9):
            y = -1.0 + i * 0.25
            glVertex2f(-1.0, y)
            glVertex2f(1.0, y)

        glEnd()

        # 中心轴稍微亮一点
        glLineWidth(1.2)
        glColor4f(0.45, 0.48, 0.55, 0.65)

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