# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: chart_value_panel.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.widgets.chart.chart_model import ChartSnapshot


class ChartValuePanel(QWidget):
    """
    图表右侧数据面板。

    显示：
    - 当前通道名称
    - 最新值
    - 当前窗口内点数
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedWidth(150)

        self.title_label = QLabel("实时数据", self)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #E6EAF2;")

        self.content_label = QLabel("--", self)
        self.content_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.content_label.setFont(QFont("Microsoft YaHei", 9))
        self.content_label.setStyleSheet("color: #C9D1D9;")
        self.content_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.content_label, 1)

        self.setStyleSheet(
            """
            ChartValuePanel {
                background-color: #151922;
                border-left: 1px solid #2A2F3A;
            }
            """
        )

    def set_snapshot(self, snapshot: ChartSnapshot | None) -> None:
        if snapshot is None or not snapshot.curves:
            self.content_label.setText("--")
            return

        lines: list[str] = []

        for curve in snapshot.curves:
            if not curve.points:
                continue

            latest = curve.points[-1].raw_y
            value_text = f"{latest:.{curve.precision}f}{curve.unit}"

            lines.append(f"{curve.name}")
            lines.append(f"  {value_text}")
            lines.append(f"  点数: {len(curve.points)}")
            lines.append("")

        self.content_label.setText("\n".join(lines).strip())