# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: start.py.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------

import sys

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MSFluentTitleBar
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import isDarkTheme
from qfluentwidgets import setTheme

from Config import AppIconPath, cfg
from app import UMainWindow

from app.Core import StyleSheet, language_manager, logger
from app.Core import load_saved_font
from app.Pages import DaplinkFlashPage, DevicePage, HomePage, PowerPage, SettingsPage


class Window(UMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("FluentAcrylicWindow")

        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.powerInterface = PowerPage(self)
        self.daplinkFlashInterface = DaplinkFlashPage(self)
        self.settingInterface = SettingsPage(self)

        self.initNavigation()
        self.initWindow()

        cfg.themeChanged.connect(self._on_theme_changed)
        self._on_theme_changed()
        StyleSheet.HOME_PAGE.apply(self.homeInterface)
        StyleSheet.SETTINGS_PAGE.apply(self.settingInterface)
        StyleSheet.DAPLINK_FLASH_PAGE.apply(self.daplinkFlashInterface)
        self._retranslate_ui()

        QTimer.singleShot(0, self._refresh_startup_theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def initNavigation(self):
        self.homeNavItem = self.addSubInterface(self.homeInterface, FIF.HOME, self.tr("Home"), FIF.HOME_FILL)
        self.deviceNavItem = self.addSubInterface(self.deviceInterface, FIF.DEVELOPER_TOOLS, self.tr("Serial"))
        self.powerNavItem = self.addSubInterface(self.powerInterface, FIF.POWER_BUTTON, self.tr("Device"))
        self.daplinkNavItem = self.addSubInterface(self.daplinkFlashInterface, FIF.IOT, "DAPLink")
        self.settingNavItem = self.addSubInterface(
            self.settingInterface,
            FIF.SETTING,
            self.tr("Settings"),
            FIF.SETTING,
            NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.setCurrentItem(self.homeInterface.objectName())

    def initWindow(self):
        self.resize(1200, 800)
        self.setTitleBar(MSFluentTitleBar(self))
        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle("Fluor4CellPower")

        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def close(self):
        logger.warning("Application closed")
        super().close()

    def closeEvent(self, event: QCloseEvent):
        try:
            if hasattr(self, "powerInterface") and self.powerInterface is not None:
                self.powerInterface.shutdown()
        except Exception as exc:
            logger.error(f"PowerPage shutdown failed during window close: {exc}")
        super().closeEvent(event)

    def _on_theme_changed(self, *_):
        dark = isDarkTheme()
        bg_color = "#1F1F1F" if dark else "#F3F3F3"
        self.setStyleSheet(f"Window {{ background: {bg_color}; }}")

    def _refresh_startup_theme(self):
        setTheme(cfg.themeMode.value)

    def _retranslate_ui(self):
        self.homeNavItem.setText(self.tr("Home"))
        self.deviceNavItem.setText(self.tr("Serial"))
        self.powerNavItem.setText(self.tr("Device"))
        self.daplinkNavItem.setText("DAPLink")
        self.settingNavItem.setText(self.tr("Settings"))
        self.setWindowTitle("Fluor4CellPower")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.LanguageChange:
            self._retranslate_ui()


if __name__ == "__main__":
    import sys
    logger.info("main is running")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    logger.info("Application started")
    try:
        app = QApplication(sys.argv)

        setTheme(cfg.themeMode.value)
        language_manager.apply_language(app)
        load_saved_font(app)

        w = Window()
        w.show()

        app.exec_()
    except Exception as e:
        logger.error(e)
