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
from typing import Iterable

from PyQt5.QtWidgets import QApplication, QWidget
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
        theme = normalizedTheme(theme)
        return str(themeQssDir(theme) / f"{self.value}.qss")


def normalizedTheme(theme=Theme.AUTO) -> Theme:
    """Return the concrete light/dark theme used for QSS lookup.

    Theme.AUTO is resolved by qfluentwidgets' current effective theme. This keeps
    startup, manual switching and following-system mode using one code path.
    """
    if theme is None:
        theme = Theme.AUTO

    if theme == Theme.AUTO:
        current = getattr(qconfig, "theme", Theme.AUTO)
        if current != Theme.AUTO:
            return current
        return Theme.DARK if isDarkTheme() else Theme.LIGHT

    return theme


def themeQssDir(theme=Theme.AUTO) -> Path:
    """Resources/Theme/qss/light or Resources/Theme/qss/dark."""
    theme = normalizedTheme(theme)
    return CTX.dirs.ThemeDir / "qss" / theme.name.lower()


def readQssFile(path: str | Path) -> str:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def defaultWindowShellQss(theme=Theme.AUTO) -> str:
    """Fallback shell QSS for MSFluentWindow chrome.

    Page QSS files live in Resources/Theme/qss, but the navigation bar and
    title bar belong to the main window shell. This fallback prevents a light
    theme from leaving those shell widgets black when Window.qss is incomplete.
    """
    theme = normalizedTheme(theme)
    if theme == Theme.DARK:
        window_bg = "#202020"
        nav_bg = "#181818"
        title_bg = "#202020"
        text = "#F5F5F5"
        sub_text = "rgba(255, 255, 255, 0.72)"
        border = "rgba(255, 255, 255, 0.10)"
    else:
        window_bg = "#F3F3F3"
        nav_bg = "#FFFFFF"
        title_bg = "#F3F3F3"
        text = "#1F1F1F"
        sub_text = "rgba(0, 0, 0, 0.68)"
        border = "rgba(0, 0, 0, 0.08)"

    return f"""
    /* built-in main window shell fallback */
    MSFluentWindow#Window, Window#Window {{
        background: {window_bg};
    }}
    QWidget#navigationInterface, NavigationInterface#navigationInterface {{
        background: {nav_bg};
        border-right: 1px solid {border};
    }}
    QWidget#titleBar, TitleBar#titleBar {{
        background: {title_bg};
        color: {text};
    }}
    QWidget#Window QLabel {{
        color: {text};
    }}
    QWidget#Window CaptionLabel {{
        color: {sub_text};
    }}
    """


def readThemeBundle(theme=Theme.AUTO, names: Iterable[str] | None = None) -> str:
    """Read a theme bundle from Resources/Theme/qss.

    When names is None, all known StyleSheet enum files are loaded in enum order.
    Missing QSS files are ignored so a theme can be partially defined.
    """
    theme = normalizedTheme(theme)
    qssDir = themeQssDir(theme)
    fileNames = list(names) if names is not None else [f"{item.value}.qss" for item in StyleSheet]

    chunks: list[str] = [defaultWindowShellQss(theme)]
    for fileName in fileNames:
        filePath = qssDir / fileName
        text = readQssFile(filePath)
        if text:
            chunks.append(f"/* {filePath.as_posix()} */\n{text}")
    return "\n\n".join(chunks)


def applyApplicationTheme(root: QWidget | None = None, theme=Theme.AUTO) -> str:
    """Apply qfluent theme and the full Resources/Theme/qss bundle.

    The returned QSS is useful for diagnostics or tests.
    """
    theme = normalizedTheme(theme)
    setTheme(theme)

    qss = readThemeBundle(theme)
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(qss)

    if root is not None:
        root.setProperty("darkTheme", theme == Theme.DARK)
        root.style().unpolish(root)
        root.style().polish(root)
        root.update()

    return qss
