# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-15 13:15
#  @FileName: start.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : Powered By GPT-5.4
#  @Python  :
# -------------------------------
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFontDatabase
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import isDarkTheme
from qfluentwidgets import MSFluentTitleBar
from qfluentwidgets import qconfig
from qfluentwidgets import setTheme

from Resources.Font import font as font_resource

from Config import AppIconPath, cfg

from app import UMainWindow
from app.Core import logger, StyleSheet, WINDOWS
from app.Core.pop_up import PopupManager
from app.Pages import DevicePage, SettingsPage, HomePage, F4CPowerPage, Stm32DownloadPage, DaplinkFlashPage


def applyGlobalEnglishFont(app: QApplication):
    """Load the bundled font and prioritize it for English text app-wide."""
    _ = font_resource
    font_path = ":/blender-pro-bold.otf"
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id == -1:
        logger.warning(f"Failed to load application font from {font_path}")
        return

    font_families = QFontDatabase.applicationFontFamilies(font_id)
    if not font_families:
        logger.warning(f"No font families found for {font_path}")
        return

    font_family = font_families[0]
    fallback_families = list(qconfig.get(qconfig.fontFamilies) or [])
    merged_families = [font_family] + [family for family in fallback_families if family != font_family]

    qconfig.set(qconfig.fontFamilies, merged_families, save=False)

    app_font = app.font()
    app_font.setFamilies(merged_families)
    app.setFont(app_font)

    logger.info(f"Application font family applied: {merged_families}")



class Window(UMainWindow):

    def __init__(self):
        super().__init__()
        self.setObjectName("FluentAcrylicWindow")
        self._manager = PopupManager(self, max_visible=6)

        WINDOWS.windows["MainWindow"] = self._manager

        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.F4CPowerInterface = F4CPowerPage()
        self.stm32DownloadInterface = Stm32DownloadPage(self)
        self.daplinkFlashInterface = DaplinkFlashPage(self)
        self.settingInterface = SettingsPage(self)

        self.initNavigation()
        self.initWindow()

        # todo 主题刷新，有无更优雅的实现呢？？？
        cfg.themeChanged.connect(self._on_theme_changed)
        self._on_theme_changed()
        StyleSheet.HOME_PAGE.apply(self.homeInterface)
        StyleSheet.SETTINGS_PAGE.apply(self.settingInterface)
        StyleSheet.STM32_DOWNLOAD_PAGE.apply(self.stm32DownloadInterface)
        StyleSheet.DAPLINK_FLASH_PAGE.apply(self.daplinkFlashInterface)

        QTimer.singleShot(0, self._refresh_startup_theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)


    def initNavigation(self):

        self.addSubInterface(self.homeInterface, FIF.HOME, '主页',FIF.HOME_FILL)
        self.addSubInterface(self.deviceInterface, FIF.DEVELOPER_TOOLS, '串口')
        self.addSubInterface(self.F4CPowerInterface, FIF.POWER_BUTTON, '设备')
        self.addSubInterface(self.stm32DownloadInterface, FIF.DOWNLOAD, '下载')
        self.addSubInterface(self.daplinkFlashInterface, FIF.IOT, 'DAPLink')
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

    def _refresh_startup_theme(self):
        """创建所有子接口后，刷新一次主题

        STM32下载页面内的一些Fluent小部件保持默认状态
        第一次暗启动时用光色板，直到主题被切换一次。
        在这里重新应用当前主题会强制这些小部件同步，没有
        更改用户保存的主题设置
        """
        setTheme(cfg.themeMode.value)


if __name__ == '__main__':
    logger.info("main is running")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    logger.info("Application started")

    app = QApplication(sys.argv)
    setTheme(cfg.themeMode.value)

    applyGlobalEnglishFont(app)

    w = Window()
    w.show()

    app.exec_()
