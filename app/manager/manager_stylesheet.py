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
# coding: utf-8
from __future__ import annotations

from enum import Enum

from config import CTX
from qfluentwidgets import StyleSheetBase, Theme, qconfig

# Mutable override for test isolation (Enum classes can't have class attrs reassigned).
_stylesheet_dirs: "DirPaths | None" = None


def set_stylesheet_dirs(dirs: "DirPaths | None"):
    """Inject DirPaths for StyleSheet.path() (test isolation).

    Pass ``None`` to revert to the default ``DirPathsInstance`` singleton.
    """
    global _stylesheet_dirs
    _stylesheet_dirs = dirs


class StyleSheet(StyleSheetBase, Enum):
    """QSS stylesheet enum using injectable or default DirPaths."""

    BATTERY_PAGE = "BatteryPage"
    DAPLINK_PAGE = "DaplinkFlashPage"
    DEVICE_PAGE = "DevicePage"
    HOME_PAGE = "HomePage"
    POWER_PAGE = "PowerPage"
    SETTINGS_PAGE = "SettingsPage"
    BASE_PAGE = "FluentAcrylicWindow"

    # Backward-compat alias for the classmethod-style injection used in tests.
    set_dirs = staticmethod(set_stylesheet_dirs)

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        dirs = _stylesheet_dirs if _stylesheet_dirs is not None else CTX.dirs
        return str(dirs.ThemeDir / "qss" / theme.name.lower() / f"{self.value}.qss")
