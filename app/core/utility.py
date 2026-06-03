# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: utility.py
#  @FileType: 核心基础设施文件，提供设备、数据和通用工具能力
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from PySide6.QtWidgets import QApplication
from qfluentwidgets import InfoBar, InfoBarManager, InfoBarPosition


_INFOBAR_MANAGER_CONFIGURED = False


def _ensure_info_bar_manager() -> None:
    global _INFOBAR_MANAGER_CONFIGURED
    if _INFOBAR_MANAGER_CONFIGURED:
        return

    manager = InfoBarManager.make(InfoBarPosition.TOP_RIGHT)
    manager.margin = 24
    manager.spacing = 12
    _INFOBAR_MANAGER_CONFIGURED = True


def showMessage(parent, title: str, content: str, level: str = "info", useSide: bool = True, autoCloseMs: int = 5000):
    _ensure_info_bar_manager()

    parent_widget = parent if parent is not None else QApplication.activeWindow()
    host_window = parent_widget.window() if parent_widget is not None else QApplication.activeWindow()
    if hasattr(host_window, "showDynamicIsland"):
        try:
            host_window.showDynamicIsland(title, content, level, min(autoCloseMs, 4200))
        except Exception:
            pass

    method = {
        "success": InfoBar.success,
        "warning": InfoBar.warning,
        "error": InfoBar.error,
    }.get((level or "info").lower(), InfoBar.info)
    return method(
        title,
        content,
        duration=autoCloseMs,
        position=InfoBarPosition.TOP_RIGHT,
        parent=parent_widget,
    )

