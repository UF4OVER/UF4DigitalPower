# coding:utf-8
import sys

from PyQt5.QtCore import Qt, QOperatingSystemVersion
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import isDarkTheme
from qfluentwidgets import MSFluentTitleBar

from app import UMainWindow, NotificationType
from Config import AppIconPath, cfg
from app.Core import logger, StyleSheet, Bus, WINDOWS
from app.Core.pop_up import PopupManager
from app.Pages import DevicePage, SettingsPage, HomePage, F4CPowerPage



class Window(UMainWindow):

    def __init__(self):
        super().__init__()

        self.setObjectName("FluentAcrylicWindow")

        self._manager = PopupManager(self, max_visible=6)

        WINDOWS.windows["MainWindow"] = self._manager


        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.F4CPowerInterface = F4CPowerPage()
        self.settingInterface = SettingsPage(self)

        self.initNavigation()
        self.initWindow()

        cfg.themeChanged.connect(self._on_theme_changed)
        self._on_theme_changed()

    def resizeEvent(self, event):
        super().resizeEvent(event)


    def initNavigation(self):

        self.addSubInterface(self.homeInterface, FIF.HOME, '主页',FIF.HOME_FILL)
        self.addSubInterface(self.deviceInterface, FIF.DEVELOPER_TOOLS, '串口')
        self.addSubInterface(self.F4CPowerInterface, FIF.POWER_BUTTON, '设备')
        self.addSubInterface(self.settingInterface,FIF.SETTING,'设置',FIF.SETTING, position=NavigationItemPosition.BOTTOM)

        self.navigationInterface.setCurrentItem(self.homeInterface.objectName())

    def initWindow(self):
        self.resize(1200, 800)

        self.setTitleBar(MSFluentTitleBar(self))

        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle('Fluor4CellPower')

        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)


    def close(self):
        logger.warning("Application closed")
        super().close()

    def _on_theme_changed(self, *_):
        dark = isDarkTheme()
        bg_color = "#1F1F1F" if dark else "#F3F3F3"
        self.setStyleSheet(f"Window {{ background: {bg_color}; }}")

        StyleSheet.HOME_PAGE.apply(self.homeInterface)


if __name__ == '__main__':
    logger.info("main is running")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    logger.info("Application started")

    app = QApplication(sys.argv)
    w = Window()
    w.show()

    app.exec_()
