# coding:utf-8
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStackedWidget, QHBoxLayout, QWidget

from qfluentwidgets import (NavigationInterface,
                            NavigationItemPosition,
                            isDarkTheme,
                            FluentWidget,
                            Theme,
                            setTheme,
                            FluentWidgetTitleBar, MSFluentWindow, FluentIconBase)
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import StandardTitleBar, FramelessWindow, AcrylicWindow

from app.Config import AppIconPath, cfg
from app.Pages import DevicePage, SettingsPage, HomePage, F4CPowerPage
from app.Core import logger, StyleSheet,Bus
from app.Pages.main_window import UMainWindow


class Window(UMainWindow):

    def __init__(self):
        super().__init__()

        self.setObjectName('Window')
        self.updateFrameless()
        # create sub interface
        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.F4CPowerInterface = F4CPowerPage()
        self.settingInterface = SettingsPage(self)

        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        # enable acrylic effect

        self.addSubInterface(self.homeInterface, FIF.HOME, '主页',FIF.HOME_FILL)
        self.addSubInterface(self.deviceInterface, FIF.DEVELOPER_TOOLS, '串口')
        self.addSubInterface(self.F4CPowerInterface, FIF.POWER_BUTTON, '设备')
        self.addSubInterface(self.settingInterface,FIF.SETTING,'设置',FIF.SETTING, position=NavigationItemPosition.BOTTOM)

        self.navigationInterface.setCurrentItem(self.homeInterface.objectName())

    def initWindow(self):
        self.resize(1200, 800)

        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle('Fluor4CellPower')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)


    def close(self):
        logger.warning("Application closed")
        super().close()


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
