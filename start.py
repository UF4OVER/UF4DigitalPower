# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: start.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------
import sys
import time

from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QCloseEvent, QIcon, QColor
from PyQt5.QtWidgets import QApplication

from qfluentwidgets import MSFluentWindow, NavigationItemPosition

from app.manager import applyApplicationTheme, loadSavedFont, logger, normalizedTheme
from app.widgets.components import DynamicIsland, createSplashScreen
from app.widgets.icon import UF4Icon
from app.widgets.pages import (
    DaplinkPage,
    DevicePage,
    HomePage,
    PowerPage,
    SettingsPage,
)

from config import AppIconPath, cfg


class Window(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("Window")

        self._initWindowShell()
        self.splashScreen = createSplashScreen(
            parent=self,
            icon=self.windowIcon(),
            title=self.windowTitle(),
            icon_size=QSize(102, 102),
            show_immediately=False,
        )
        self.splashScreen.show()
        self.show()
        QApplication.processEvents()

        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.powerInterface = PowerPage(self)
        self.daplinkInterface = DaplinkPage(self)
        self.settingInterface = SettingsPage(self)

        self.__initNavigation()
        self.__initWindow()
        self._onThemeChanged()
        cfg.themeChanged.connect(self._onThemeChanged)
        self.splashScreen.finish()

        QTimer.singleShot(150, self._checkUpdateOnStartUp)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "dynamicIsland"):
            self.dynamicIsland.recenter()

    def _initWindowShell(self):
        self.resize(1400, 1100)
        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle("UF4 POWER")
        self._centerOnScreen()

    def _centerOnScreen(self):
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def __initNavigation(self):
        self.homeNavItem = self.addSubInterface(
            self.homeInterface,
            UF4Icon.GAUGE,
            '引导',
            UF4Icon.GAUGE_FILL
        )
        self.deviceNavItem = self.addSubInterface(
            self.deviceInterface,
            UF4Icon.SERIAL_PORT,
            '串口',
            UF4Icon.SERIAL_PORT_FILL
        )
        self.powerNavItem = self.addSubInterface(
            self.powerInterface,
            UF4Icon.DEVELOPER_BOARD,
            '设备',
            UF4Icon.DEVELOPER_BOARD_FILL
        )

        self.daplinkNavItem = self.addSubInterface(
            self.daplinkInterface,
            UF4Icon.FLASH_SETTINGS,
            '烧录',
            UF4Icon.FLASH_SETTINGS_FILL
        )
        self.settingNavItem = self.addSubInterface(
            self.settingInterface,
            UF4Icon.SERVER,
            '设置',
            UF4Icon.SERVER_FILL,
            NavigationItemPosition.BOTTOM
        )
        self.navigationInterface.setCurrentItem(self.homeInterface.objectName())

    def __initWindow(self):
        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        self.dynamicIsland = DynamicIsland(self.titleBar)
        self.dynamicIsland.recenter()
        self.dynamicIsland.raise_()

    def close(self):
        logger.warning("Application closed")
        super().close()

    def closeEvent(self, event: QCloseEvent):
        self.powerInterface.shutdown()
        super().closeEvent(event)

    def _onThemeChanged(self, *_):
        theme = normalizedTheme(cfg.themeMode.value)
        is_dark = theme.name.lower() == "dark"
        bg_light = QColor("#F3F3F3")
        bg_dark = QColor("#242424")

        applyApplicationTheme(self, theme)
        self.setCustomBackgroundColor(bg_light, bg_dark)
        self.setMicaEffectEnabled(False)
        # self.titleBar.setStyleSheet("background: transparent;")
        self.dynamicIsland.setDarkTheme(is_dark)

        shell_bg = "#242424" if is_dark else "#F3F3F3"
        nav_bg = "#1F1F1F" if is_dark else "#FFFFFF"
        title_bg = shell_bg
        text = "#F5F5F5" if is_dark else "#1F1F1F"
        border = "rgba(255,255,255,0.10)" if is_dark else "rgba(0,0,0,0.08)"
        self.setStyleSheet(f"""
            MSFluentWindow#Window {{ background: {shell_bg}; }}
            QWidget#navigationInterface {{
                background: {nav_bg};
                border-right: 1px solid {border};
            }}
            QWidget#titleBar {{
                background: {title_bg};
                color: {text};
            }}
        """)
        self.navigationInterface.setStyleSheet(f"background: {nav_bg}; border-right: 1px solid {border};")
        self.titleBar.setStyleSheet(f"background: {title_bg}; color: {text};")

        for widget in (self, self.navigationInterface, self.titleBar):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        for page in (
            self.homeInterface,
            self.deviceInterface,
            self.powerInterface,
            self.daplinkInterface,
            self.settingInterface,
        ):
            if hasattr(page, "_onThemeChanged"):
                page._onThemeChanged()

    def showDynamicIsland(self, title: str, content: str = "", level: str = "info", duration: int = 3200):
        if hasattr(self, "dynamicIsland"):
            self.dynamicIsland.notify(title, content, level, duration)

    def _checkUpdateOnStartUp(self):
        if getattr(cfg.checkUpdateAtStartUp, "value", False):
            self.homeInterface.requestUpdateCheck(manual=False)


if __name__ == "__main__":
    logger.info("main is running")

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    logger.info("Application started")
    try:
        time_ = time.time()
        app = QApplication(sys.argv)

        loadSavedFont(app)  # 加载字体

        applyApplicationTheme(theme=cfg.themeMode.value)  # 加载主题

        w = Window()

        w.setMicaEffectEnabled(True)

        logger.info(f"start time: {time.time() - time_}")

        app.exec_()
    except Exception as e:
        logger.error(e)
