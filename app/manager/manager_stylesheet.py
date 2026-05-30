# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-09 11:50
#  @FileName: manager_stylesheet.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------
from __future__ import annotations

from enum import Enum
from pathlib import Path

from PyQt5.QtWidgets import QWidget
from config import CTX
from qfluentwidgets import StyleSheetBase, Theme, isDarkTheme, qconfig, setTheme


class StyleSheet(StyleSheetBase, Enum):
    """QSS stylesheet enum using Resources/Theme/qss/<theme>/*.qss."""

    BATTERY_PAGE = "BatteryPage"
    DAPLINK_PAGE = "DaplinkFlashPage"
    DEVICE_PAGE = "DevicePage"
    HOME_PAGE = "HomePage"
    POWER_PAGE = "PowerPage"
    SETTINGS_PAGE = "SettingsPage"
    BASE_PAGE = "Window"

    def path(self, theme=Theme.AUTO):
        theme = CTX.qcfg.theme if theme == Theme.AUTO else theme
        return f":{CTX.dirs.ThemeDir}/qss/{theme.value.lower()}/{self.value}.qss"


