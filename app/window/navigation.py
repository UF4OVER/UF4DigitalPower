# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import FluentIconBase, NavigationItemPosition

from app.widgets.icon import UF4Icon
from app.widgets.pages import (
    DaplinkPage,
    DevicePage,
    HomePage,
    PowerPage,
    SettingsPage,
)


@dataclass(frozen=True)
class NavigationEntry:
    attr_name: str
    interface_attr: str
    icon: FluentIconBase | QIcon | str
    text: str
    selected_icon: FluentIconBase | QIcon | str
    position: NavigationItemPosition = NavigationItemPosition.TOP


NAVIGATION_ENTRIES = (
    NavigationEntry("homeNavItem"   ,  "homeInterface"   , UF4Icon.GAUGE, "引导", UF4Icon.GAUGE_FILL),
    NavigationEntry("deviceNavItem" ,  "deviceInterface" , UF4Icon.SERIAL_PORT, "串口", UF4Icon.SERIAL_PORT_FILL),
    NavigationEntry("powerNavItem"  ,  "powerInterface"  , UF4Icon.DEVELOPER_BOARD, "设备", UF4Icon.DEVELOPER_BOARD_FILL),
    NavigationEntry("daplinkNavItem",  "daplinkInterface", UF4Icon.FLASH_SETTINGS, "烧录", UF4Icon.FLASH_SETTINGS_FILL),
    NavigationEntry("settingNavItem",  "settingInterface", UF4Icon.SERVER,"设置", UF4Icon.SERVER_FILL,NavigationItemPosition.BOTTOM),
)


class NavigationMixin:
    """Page construction and navigation registration."""

    homeInterface: HomePage
    deviceInterface: DevicePage
    powerInterface: PowerPage
    daplinkInterface: DaplinkPage
    settingInterface: SettingsPage

    def createPages(self) -> None:
        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.powerInterface = PowerPage(self)
        self.daplinkInterface = DaplinkPage(self)
        self.settingInterface = SettingsPage(self)

    def registerNavigation(self) -> None:
        for entry in NAVIGATION_ENTRIES:
            interface = getattr(self, entry.interface_attr)
            self._addNavigationEntry(entry, interface)

        self.navigationInterface.setCurrentItem(self.homeInterface.objectName())

    def _addNavigationEntry(self, entry: NavigationEntry, interface: QWidget) -> None:
        item = self.addSubInterface(
            interface,
            entry.icon,
            entry.text,
            entry.selected_icon,
            entry.position,
        )
        setattr(self, entry.attr_name, item)
