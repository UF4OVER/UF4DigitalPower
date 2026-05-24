# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout
from qfluentwidgets import PushButton, PrimaryPushButton, isDarkTheme


class ChartControlPanel(QWidget):
    """
    图表控制面板。

    对外只发出 groupChanged / exportRequested，具体 DataHub 和 ChartModel
    过滤逻辑由 RealtimeChartWidget 统一处理。
    """

    groupChanged = pyqtSignal(object)
    exportRequested = pyqtSignal()

    _GROUPS = (
        ("all", "全部", None),
        ("voltage", "电压", {"voltage"}),
        ("current", "电流", {"current"}),
        ("power", "功率", {"power"}),
        ("thermal", "温度", {"thermal"}),
        ("efficiency", "效率", {"efficiency"}),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChartControlPanel")
        self._buttons: dict[str, PushButton] = {}
        self._current_key = "all"
        self.export_button: PushButton | None = None
        self._init_ui()
        self.refreshTheme()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        for key, text, groups in self._GROUPS:
            button = PushButton(text, self)
            button.setCheckable(True)
            button.setFixedHeight(30)
            button.clicked.connect(
                lambda checked=False, k=key, g=groups: self._select_group(k, g)
            )
            self._buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)

        self.export_button = PrimaryPushButton("导出图片", self)
        self.export_button.setFixedHeight(30)
        self.export_button.clicked.connect(self.exportRequested.emit)
        layout.addWidget(self.export_button)

        self._update_button_state()

    def _select_group(self, key: str, groups: set[str] | None) -> None:
        self._current_key = key
        self._update_button_state()
        self.groupChanged.emit(groups)

    def setCurrentGroup(self, key: str) -> None:
        keys = {item[0] for item in self._GROUPS}
        if key not in keys:
            key = "all"
        self._current_key = key
        self._update_button_state()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        bg = "rgba(31, 35, 44, 0.72)" if dark else "rgba(255, 255, 255, 0.72)"
        border = "rgba(255, 255, 255, 0.08)" if dark else "rgba(15, 23, 42, 0.08)"
        self.setStyleSheet(
            f"""
            QWidget#ChartControlPanel {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            """
        )
        self._update_button_state()

    def _update_button_state(self) -> None:
        dark = isDarkTheme()
        normal_bg = "rgba(255, 255, 255, 0.06)" if dark else "rgba(15, 23, 42, 0.035)"
        normal_fg = "#D8DEE9" if dark else "#334155"
        normal_border = "rgba(255, 255, 255, 0.10)" if dark else "rgba(15, 23, 42, 0.10)"
        hover_bg = "rgba(255, 255, 255, 0.10)" if dark else "rgba(15, 23, 42, 0.065)"
        active_bg = "#3A7AFE"

        for key, button in self._buttons.items():
            checked = key == self._current_key
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
            if checked:
                button.setStyleSheet(
                    f"""
                    PushButton {{
                        background: {active_bg};
                        color: white;
                        border: 1px solid {active_bg};
                        border-radius: 8px;
                        padding: 4px 12px;
                        font-weight: 600;
                    }}
                    """
                )
            else:
                button.setStyleSheet(
                    f"""
                    PushButton {{
                        background: {normal_bg};
                        color: {normal_fg};
                        border: 1px solid {normal_border};
                        border-radius: 8px;
                        padding: 4px 12px;
                    }}
                    PushButton:hover {{
                        background: {hover_bg};
                    }}
                    """
                )
