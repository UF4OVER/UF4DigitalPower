# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: chart_value_panel.py
#  @FileType: 图表组件文件，负责实时曲线、图表模型和数据展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, StrongBodyLabel, isDarkTheme, setFont

from app.widgets.chart.chart_model import ChartSnapshot


class ChartValuePanel(QWidget):
    """
    图表右侧数据面板。

    标签统一使用 qfluentwidgets Label，背景透明，仅文字颜色跟随主题。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChartValuePanel")
        self.setFixedWidth(168)

        self.title_label = StrongBodyLabel("实时数据", self)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        setFont(self.title_label, 14, QFont.DemiBold)

        self.range_label = CaptionLabel("--", self)
        self.range_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.range_label.setFont(QFont("Consolas", 8))
        self.range_label.setWordWrap(True)

        self.content_label = BodyLabel("--", self)
        self.content_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.content_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 4, 8)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.range_label)
        layout.addWidget(self.content_label, 1)

        self.refreshTheme()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        title = "#F5F7FA" if dark else "#111827"
        text = "#D1D5DB" if dark else "#334155"
        muted = "#9CA3AF" if dark else "#64748B"
        self.setStyleSheet("QWidget#ChartValuePanel { background: transparent; border: none; }")
        self.title_label.setStyleSheet(f"background: transparent; color: {title};")
        self.content_label.setStyleSheet(f"background: transparent; color: {text};")
        self.range_label.setStyleSheet(f"background: transparent; color: {muted};")

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
