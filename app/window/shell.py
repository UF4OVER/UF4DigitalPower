# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QIcon

from config import AppIconPath


class WindowShellMixin:
    """Window size, title, icon, and screen placement."""

    def initWindowShell(self) -> None:
        self.resize(1400, 1100)
        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle("F4CP")
        self.centerOnScreen()

    def centerOnScreen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        desktop = screen.availableGeometry()
        self.move(
            desktop.x() + desktop.width() // 2 - self.width() // 2,
            desktop.y() + desktop.height() // 2 - self.height() // 2,
        )
