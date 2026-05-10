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

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import QApplication

from qfluentwidgets import FluentIcon as FIF, MSFluentWindow
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import isDarkTheme
from qfluentwidgets import setTheme

from Config import AppIconPath, cfg

from App.Core import StyleSheet, logger, load_saved_font
from App.Pages import BatteryPage, DaplinkPage, DevicePage, HomePage, PowerPage, SettingsPage
from Core import UF4Icon


class Window(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("FluentAcrylicWindow")

        # self.setFixedSize(1200, 800)

        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.powerInterface = PowerPage(self)
        self.batteryInterface = BatteryPage(self)
        self.daplinkInterface = DaplinkPage(self)
        self.settingInterface = SettingsPage(self)

        self.__initNavigation()
        self.__initWindow()

        self._onThemeChanged()

        cfg.themeChanged.connect(self._onThemeChanged)

        StyleSheet.HOME_PAGE.apply(self.homeInterface)
        StyleSheet.DEVICE_PAGE.apply(self.deviceInterface)
        StyleSheet.BATTERY_PAGE.apply(self.batteryInterface)
        StyleSheet.SETTINGS_PAGE.apply(self.settingInterface)
        StyleSheet.DAPLINK_PAGE.apply(self.daplinkInterface)

        QTimer.singleShot(0, self._refreshStartupTheme)
        QTimer.singleShot(150, self._checkUpdateOnStartUp)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def __initNavigation(self):
        self.homeNavItem = self.addSubInterface(
            self.homeInterface, FIF.HOME, '主页', FIF.HOME_FILL
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
        self.batteryNavItem = self.addSubInterface(
            self.batteryInterface,
            UF4Icon.BATTERY_SAVER,
            '电池',
            UF4Icon.BATTERY_SAVER_FILL
        )
        self.daplinkNavItem = self.addSubInterface(
            self.daplinkInterface,
            UF4Icon.FLASH_SETTINGS,
            '烧录',
            UF4Icon.FLASH_SETTINGS_FILL

        )
        self.settingNavItem = self.addSubInterface(
            self.settingInterface,
            FIF.SETTING,
            '设置',
            FIF.SETTING,
            NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.setCurrentItem(self.homeInterface.objectName())

    def __initWindow(self):
        self.resize(1400, 1100)
        # self.setTitleBar(FluentWidgetTitleBar(self))
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

    def _onThemeChanged(self, *_):
        dark = isDarkTheme()
        bgColor = "#1F1F1F" if dark else "#F3F3F3"
        self.setStyleSheet(f"Window {{ background: {bgColor}; }}")

    def _refreshStartupTheme(self):
        setTheme(cfg.themeMode.value)

    def _checkUpdateOnStartUp(self):
        if getattr(cfg.checkUpdateAtStartUp, "value", False):
            self.homeInterface.requestUpdateCheck(manual=False)


if __name__ == "__main__":
    import sys

    logger.info("main is running")

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    logger.info("Application started")
    try:
        app = QApplication(sys.argv)

        # setTheme(cfg.themeMode.value)
        load_saved_font(app)

        w = Window()
        w.show()

        app.exec_()
    except Exception as e:
        logger.error(e)
