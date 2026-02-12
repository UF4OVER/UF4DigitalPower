# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-09 11:50
#  @FileName: set_stylesheet.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------
# coding: utf-8
from enum import Enum

from app.Config import SettingMangerInstance as SMI
from qfluentwidgets import StyleSheetBase, Theme, qconfig


class StyleSheet(StyleSheetBase, Enum):  # 重写 StyleSheetBase 以支持枚举成员

    # Core pages present in app/Pages
    HOME_PAGE = "HomePage"
    SETTINGS_PAGE = "SettingsPage"
    DEVICE_PAGE = "DevicePage"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return str(SMI.ThemeDir / "qss" / theme.name.lower() / f"{self.value}.qss")
