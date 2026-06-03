# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from config import AppIconPath


class WindowShellMixin:
    """Window size, title, icon, and screen placement."""

    def initWindowShell(self) -> None:
        self.resize(1400, 1100)
        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle("F4CP")
        self.centerOnScreen()

    def centerOnScreen(self) -> None:
        desktop = QApplication.desktop().availableGeometry()
        self.move(
            desktop.width() // 2 - self.width() // 2,
            desktop.height() // 2 - self.height() // 2,
        )
