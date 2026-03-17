# coding:utf-8
import sys

from PyQt5.QtCore import Qt, QOperatingSystemVersion, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import isDarkTheme
from qframelesswindow import StandardTitleBar, AcrylicWindow

from app import UMainWindow, NotificationType
from app.Config import AppIconPath, cfg
from app.Core import logger, StyleSheet, Bus, WINDOWS
from app.Core.pop_up import PopupManager
from app.Pages import DevicePage, SettingsPage, HomePage, F4CPowerPage



class Window(UMainWindow):

    def __init__(self):
        super().__init__()

        self.setObjectName("FluentAcrylicWindow")

        self._manager = PopupManager(self, max_visible=6)
        self._acrylic_enabled = False

        WINDOWS.windows["MainWindow"] = self._manager


        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.F4CPowerInterface = F4CPowerPage()
        self.settingInterface = SettingsPage(self)

        self.initNavigation()
        self.initWindow()

        Bus.enableAcrylicBackground.connect(self.setAcrylicEffectEnabled)
        Bus.enableAcrylicBackground.connect(self._on_acrylic_background_changed)
        cfg.themeChanged.connect(self._on_theme_changed)

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

        self.setTitleBar(StandardTitleBar(self))

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

    def setAcrylicEffectEnabled(self, enable: bool):
        """Set acrylic effect enabled with theme-aware contrast."""
        self._acrylic_enabled = enable
        dark = isDarkTheme()

        if enable:
            # Dark theme needs a deeper tint to keep white text readable.
            acrylic_color = "202020CC" if dark else "F2F2F299"
            self.setStyleSheet("background: transparent")
            self.windowEffect.setAcrylicEffect(self.winId(), acrylic_color)

            if QOperatingSystemVersion.current() != QOperatingSystemVersion.Windows10:
                self.windowEffect.addShadowEffect(self.winId())
        else:
            fallback_bg = "#1F1F1F" if dark else "#F2F2F2"
            self.setStyleSheet(f"background:{fallback_bg}")
            self.windowEffect.addShadowEffect(self.winId())
            self.windowEffect.removeBackgroundEffect(self.winId())

        StyleSheet.HOME_PAGE.apply(self.homeInterface)
        StyleSheet.DEVICE_PAGE.apply(self.deviceInterface)
        StyleSheet.SETTINGS_PAGE.apply(self.settingInterface)

    def _on_theme_changed(self, *_):
        """Re-apply acrylic colors after theme switches."""
        self.setAcrylicEffectEnabled(self._acrylic_enabled)

    def _on_acrylic_background_changed(self, enabled: bool):
        state_text = "enabled" if enabled else "disabled"
        self._manager.push(
            NotificationType.Information,
            "System",
            f"Acrylic background {state_text}",
            2100,
        )


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
