# -*- coding: utf-8 -*-
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
    BASE_PAGE = "Base"

    def path(self, theme=Theme.AUTO):
        theme = CTX.cfg.theme if theme == Theme.AUTO else theme
        return str(CTX.dirs.ThemeDir / "qss" / theme.value.lower() / f"{self.value}.qss")
