# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: chart_control_panel.py
#  @FileType: 图表组件文件，负责实时曲线、图表模型和数据展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout
from qfluentwidgets import PillPushButton, PrimaryPushButton


class ChartControlPanel(QWidget):
    """
    图表控制面板。

    所有按钮使用 qfluentwidgets 控件，不再手写按钮 QSS。
    """

    groupChanged = Signal(object)
    exportRequested = Signal()

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
        self._buttons: dict[str, PillPushButton] = {}
        self._current_key = "all"
        self.export_button: PrimaryPushButton | None = None
        self._init_ui()
        self.refreshTheme()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for key, text, groups in self._GROUPS:
            button = PillPushButton(text, self)
            button.setCheckable(True)
            button.setFixedHeight(32)
            button.clicked.connect(lambda checked=False, k=key, g=groups: self._select_group(k, g))
            self._buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)

        self.export_button = PrimaryPushButton("导出图片", self)
        self.export_button.setFixedHeight(32)
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
        self.setStyleSheet("QWidget#ChartControlPanel { background: transparent; border: none; }")
        self._update_button_state()

    def _update_button_state(self) -> None:
        for key, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(key == self._current_key)
            button.blockSignals(False)
