# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from qfluentwidgets import isDarkTheme

from app.widgets.chart.chart_model import ChartSnapshot


class ChartValuePanel(QWidget):
    """
    图表右侧数据面板。

    显示当前窗口内每个通道的最新值、点数和 Y 轴范围，
    颜色跟随 qfluentwidgets 亮/暗主题。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChartValuePanel")
        self.setFixedWidth(168)

        self.title_label = QLabel("实时数据", self)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))

        self.range_label = QLabel("--", self)
        self.range_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.range_label.setFont(QFont("Consolas", 8))
        self.range_label.setWordWrap(True)

        self.content_label = QLabel("--", self)
        self.content_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.content_label.setFont(QFont("Microsoft YaHei", 9))
        self.content_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.range_label)
        layout.addWidget(self.content_label, 1)

        self.refreshTheme()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        bg = "rgba(21, 25, 34, 0.92)" if dark else "rgba(248, 250, 252, 0.92)"
        border = "rgba(255, 255, 255, 0.08)" if dark else "rgba(15, 23, 42, 0.08)"
        title = "#F5F7FA" if dark else "#111827"
        text = "#C9D1D9" if dark else "#334155"
        muted = "#8B95A5" if dark else "#64748B"
        self.setStyleSheet(
            f"""
            QWidget#ChartValuePanel {{
                background: {bg};
                border-left: 1px solid {border};
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        self.title_label.setStyleSheet(f"color: {title};")
        self.content_label.setStyleSheet(f"color: {text};")
        self.range_label.setStyleSheet(f"color: {muted};")

    def set_snapshot(self, snapshot: ChartSnapshot | None) -> None:
        if snapshot is None or not snapshot.curves:
            self.range_label.setText("--")
            self.content_label.setText("--")
            return

        self.range_label.setText(
            f"X {snapshot.x_range.span:.1f}s\n"
            f"Y {snapshot.y_range.minimum:.2f} ~ {snapshot.y_range.maximum:.2f}"
        )

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

        self.content_label.setText("\n".join(lines).strip() or "--")
