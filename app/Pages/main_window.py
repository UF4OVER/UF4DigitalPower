# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 02-15 17:08
#  @FileName: main_window.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------
from typing import Optional, Union

from PyQt5.QtCore import QRect, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QApplication
from qfluentwidgets import (
    FluentIconBase,
    FluentStyleSheet,
    FluentWidget,
    NavigationBar,
    NavigationBarPushButton,
    NavigationItemPosition,
    qrouter,
)
from qfluentwidgets.window.stacked_widget import StackedWidget

NavigationIcon = Union[FluentIconBase, QIcon, str]


class UMainWindow(FluentWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.hBoxLayout = QHBoxLayout(self)
        self.stackedWidget = StackedWidget(self)
        self.navigationInterface = NavigationBar(self)
        self._currentChangedConnected = False

        self._initLayout()

    def _initLayout(self):
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 48, 0, 0)
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackedWidget, 1)

        FluentStyleSheet.FLUENT_WINDOW.apply(self.stackedWidget)

    def addSubInterface(
        self,
        interface: QWidget,
        icon: NavigationIcon,
        text: str,
        selectedIcon: Optional[NavigationIcon] = None,
        position=NavigationItemPosition.TOP,
        isTransparent=False,
    ) -> NavigationBarPushButton:
        """add sub interface, the object name of `interface` should be set already
        before calling this method

        Parameters
        ----------
        interface: QWidget
            the subinterface to be added

        icon: FluentIconBase | QIcon | str
            the icon of navigation item

        text: str
            the text of navigation item

        selectedIcon: str | QIcon | FluentIconBase
            the icon of navigation item in selected state

        position: NavigationItemPosition
            the position of navigation item
        """
        routeKey = self._validateInterface(interface)

        interface.setProperty("isStackedTransparent", isTransparent)
        self.stackedWidget.addWidget(interface)

        item = self.navigationInterface.addItem(
            routeKey=routeKey,
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            selectedIcon=selectedIcon,
            position=position,
        )

        if self.stackedWidget.count() == 1:
            self._initFirstInterface(routeKey)

        self._updateStackedBackground()

        return item

    def removeInterface(self, interface: QWidget, isDelete=False):
        routeKey = self._validateInterface(interface)

        self.navigationInterface.removeWidget(routeKey)
        self.stackedWidget.removeWidget(interface)
        interface.hide()

        if isDelete:
            interface.deleteLater()

    def switchTo(self, interface: QWidget):
        self.stackedWidget.setCurrentWidget(interface, popOut=False)

    def _onCurrentInterfaceChanged(self, index: int):
        widget = self.stackedWidget.widget(index)
        if widget is None:
            return

        self.navigationInterface.setCurrentItem(widget.objectName())
        qrouter.push(self.stackedWidget, widget.objectName())

        self._updateStackedBackground()

    def _updateStackedBackground(self):
        currentWidget = self.stackedWidget.currentWidget()
        if currentWidget is None:
            return

        isTransparent = bool(currentWidget.property("isStackedTransparent"))
        if bool(self.stackedWidget.property("isTransparent")) == isTransparent:
            return

        self.stackedWidget.setProperty("isTransparent", isTransparent)
        self.stackedWidget.setStyle(QApplication.style())

    def _initFirstInterface(self, routeKey: str):
        if not self._currentChangedConnected:
            self.stackedWidget.currentChanged.connect(self._onCurrentInterfaceChanged)
            self._currentChangedConnected = True

        self.navigationInterface.setCurrentItem(routeKey)
        qrouter.setDefaultRouteKey(self.stackedWidget, routeKey)

    @staticmethod
    def _validateInterface(interface: QWidget) -> str:
        routeKey = interface.objectName()
        if not routeKey:
            raise ValueError("The object name of `interface` can't be empty string.")

        return routeKey

    def systemTitleBarRect(self, size: QSize) -> QRect:
        """Returns the system title bar rect, only works for macOS

        Parameters
        ----------
        size: QSize
            original system title bar rect
        """
        return QRect(
            size.width() - 75, 0 if self.isFullScreen() else 8, 75, size.height()
        )
