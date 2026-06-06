# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: manager_stylesheet.py
#  @FileType: 样式管理文件，负责 Fluent 主题样式加载
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from enum import Enum

from qfluentwidgets import StyleSheetBase, Theme

from config import CTX


class StyleSheet(StyleSheetBase, Enum):
    BATTERY_PAGE = "BatteryPage"
    DAPLINK_PAGE = "DaplinkFlashPage"
    DEVICE_PAGE = "DevicePage"
    HOME_PAGE = "HomePage"
    POWER_PAGE = "PowerPage"
    SETTINGS_PAGE = "SettingsPage"
    VERSION_PAGE = "VersionPage"
    BASE_PAGE = "Base"

    def path(self, theme=Theme.AUTO):
        theme = CTX.cfg.theme if theme == Theme.AUTO else theme
        return str(CTX.dirs.ThemeDir / "qss" / theme.value.lower() / f"{self.value}.qss")
