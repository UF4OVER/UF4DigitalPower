# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import MSFluentWindow

from app.widgets.components import DynamicIsland, createSplashScreen

from .navigation import NavigationMixin
from .shell import WindowShellMixin
from .theme import ThemeBackgroundMixin


class Window(WindowShellMixin, NavigationMixin, ThemeBackgroundMixin, MSFluentWindow):
    """Main application window, composed from focused window concerns."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Window")
        self.initWindowShell()
        self.splashScreen = createSplashScreen(
            parent=self,
            icon=self.windowIcon(),
            title=self.windowTitle(),
            icon_size=QSize(300, 300),
            show_immediately=False,
        )
        self.splashScreen.show()
        self.show()
        QApplication.processEvents()

        self.createPages()
        self.registerNavigation()
        self.initTitleOverlay()
        self.initThemeBackground()
        self.splashScreen.finish()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "dynamicIsland"):
            self.dynamicIsland.recenter()

    def initTitleOverlay(self) -> None:
        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        self.dynamicIsland = DynamicIsland(self.titleBar)
        self.dynamicIsland.recenter()
        self.dynamicIsland.raise_()

    def showDynamicIsland(self, title: str, content: str = "", level: str = "info", duration: int = 3200):
        if hasattr(self, "dynamicIsland"):
            self.dynamicIsland.notify(title, content, level, duration)
