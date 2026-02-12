# coding:utf-8
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStackedWidget, QHBoxLayout

from qfluentwidgets import (NavigationInterface,
                            NavigationItemPosition,
                            isDarkTheme,
                            FluentWidget,
                            Theme,
                            setTheme,
                            FluentWidgetTitleBar)
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import StandardTitleBar, FramelessWindow

from app.Config import AppIconPath, cfg
from app.Pages import DevicePage, SettingsPage, HomePage, F4CPpowerPage
from app.Core import logger, StyleSheet


class Window(FluentWidget):

    def __init__(self):
        super().__init__()

        self.setTitleBar(FluentWidgetTitleBar(self))

        self.hBoxLayout = QHBoxLayout(self)
        self.navigationInterface = NavigationInterface(self, showMenuButton=True)
        self.stackWidget = QStackedWidget(self)

        # create sub interface
        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.F4CPpowerInterface = F4CPpowerPage(self) # F4CP power page will be implemented in the future

        self.settingInterface = SettingsPage(self)

        self.initLayout()
        self.initNavigation()
        self.initWindow()

    def initLayout(self):
        self.hBoxLayout.setSpacing(1)
        self.hBoxLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)

        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackWidget)

        self.hBoxLayout.setStretchFactor(self.stackWidget, 1)

    def initNavigation(self):
        # enable acrylic effect
        self.navigationInterface.setAcrylicEnabled(True)


        self.addSubInterface(
            self.homeInterface,
            FIF.HOME,
            "主页")
        self.addSubInterface(
            self.deviceInterface,
            FIF.DEVELOPER_TOOLS,
            'TVLCOM')
        self.addSubInterface(
            self.F4CPpowerInterface,
            FIF.POWER_BUTTON,
            'F4CP Power',
        )

        self.navigationInterface.addSeparator()

        self.addSubInterface(
            self.settingInterface,
            FIF.SETTING,
            '设置',
            NavigationItemPosition.BOTTOM)

        self.stackWidget.currentChanged.connect(self.onCurrentInterfaceChanged)
        self.stackWidget.setCurrentIndex(0)

    def initWindow(self):
        self.resize(1200, 800)
        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle('Fluor4CellPower')

        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def addSubInterface(self, interface, icon, text: str, position=NavigationItemPosition.TOP, parent=None):
        """ add sub interface """
        self.stackWidget.addWidget(interface)
        self.navigationInterface.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            position=position,
            tooltip=text,
            parentRouteKey=parent.objectName() if parent else None
        )

    def switchTo(self, widget):
        self.stackWidget.setCurrentWidget(widget)

    def onCurrentInterfaceChanged(self, index):
        widget = self.stackWidget.widget(index)
        self.navigationInterface.setCurrentItem(widget.objectName())


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    logger.info("Application started")
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
