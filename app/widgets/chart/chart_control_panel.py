# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/24
#  @FileName: chart_control_panel.py.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton


class ChartControlPanel(QWidget):
    """
    图表控制面板。

    第一版功能：
    - 切换显示全部通道
    - 切换显示电压组
    - 切换显示电流组
    - 切换显示功率组
    - 切换显示温度组
    - 切换显示效率组
    """

    groupChanged = pyqtSignal(object)
    exportRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._buttons: dict[str, QPushButton] = {}
        self._current_key = "all"

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._add_button(layout, "all", "全部", None)
        self._add_button(layout, "voltage", "电压", {"voltage"})
        self._add_button(layout, "current", "电流", {"current"})
        self._add_button(layout, "power", "功率", {"power"})
        self._add_button(layout, "thermal", "温度", {"thermal"})
        self._add_button(layout, "efficiency", "效率", {"efficiency"})

        layout.addStretch(1)

        export_button = QPushButton("导出图片", self)
        export_button.clicked.connect(self.exportRequested.emit)
        export_button.setStyleSheet(
            """
            QPushButton {
                background-color: #232A36;
                color: #E6EAF2;
                border: 1px solid #3A3F4B;
                border-radius: 6px;
                padding: 6px 12px;
            }

            QPushButton:hover {
                background-color: #303849;
            }
            """
        )
        layout.addWidget(export_button)
        self._update_button_state()

    def _add_button(
        self,
        layout: QHBoxLayout,
        key: str,
        text: str,
        groups: set[str] | None,
    ) -> None:
        button = QPushButton(text, self)
        button.setCheckable(True)
        button.clicked.connect(lambda checked=False, k=key, g=groups: self._select_group(k, g))

        self._buttons[key] = button
        layout.addWidget(button)

    def _select_group(self, key: str, groups: set[str] | None) -> None:
        self._current_key = key
        self._update_button_state()
        self.groupChanged.emit(groups)

    def _update_button_state(self) -> None:
        for key, button in self._buttons.items():
            button.setChecked(key == self._current_key)

            if key == self._current_key:
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #3A7AFE;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                    }
                    """
                )
            else:
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #2B2F3A;
                        color: #D8DEE9;
                        border: 1px solid #3A3F4B;
                        border-radius: 6px;
                        padding: 6px 12px;
                    }

                    QPushButton:hover {
                        background-color: #363C49;
                    }
                    """
                )