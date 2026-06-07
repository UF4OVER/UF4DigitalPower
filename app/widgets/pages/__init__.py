# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: __init__.py
#  @FileType: 页面包初始化文件，集中导出主界面页面
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel
from qfluentwidgets import isDarkTheme

from .page_device import *
from .page_daplink import *
from .page_home import *
from . import page_power as _page_power
from .page_power import *
from .page_settings import *
from .page_battery import *
from .page_version import *


class _SafeStatusChip(QLabel):
    """QLabel based status chip, avoiding qfluent PillPushButton style recursion."""

    def __init__(self, text: str = "离线", parent=None):
        super().__init__(text, parent)
        self._online = False
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(30)
        self.setMinimumWidth(86)
        self.refreshTheme()

    def setOnline(self, online: bool) -> None:
        self._online = bool(online)
        self.setText("在线" if self._online else "离线")
        self.refreshTheme()

    def refreshTheme(self) -> None:
        dark = isDarkTheme()
        if self._online:
            background = "rgba(34, 197, 94, 0.22)"
            foreground = "#22C55E" if dark else "#166534"
            border = "rgba(34, 197, 94, 0.36)"
        else:
            background = "rgba(239, 68, 68, 0.20)"
            foreground = "#F87171" if dark else "#B91C1C"
            border = "rgba(239, 68, 68, 0.34)"
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {background};
                color: {foreground};
                border: 1px solid {border};
                border-radius: 14px;
                padding-left: 12px;
                padding-right: 12px;
                font-weight: 700;
            }}
            """
        )


_page_power.StatusChip = _SafeStatusChip
StatusChip = _SafeStatusChip
