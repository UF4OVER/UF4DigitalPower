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

from PyQt5.QtCore import QEasingCurve, QEventLoop, QPropertyAnimation, Qt, QTimer, QSize
from PyQt5.QtGui import QCloseEvent, QIcon, QPixmap, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from qfluentwidgets import MSFluentWindow
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import ProgressBar
from qfluentwidgets import isDarkTheme
from qfluentwidgets import setTheme

from qframelesswindow import FramelessWindow

from config import AppIconPath, CTX, cfg

from app.manager import StyleSheet, logger

from app.widgets.icon import UF4Icon
from app.widgets.pages import DaplinkPage, DevicePage, HomePage, PowerPage, SettingsPage


class StartupSplashWindow(FramelessWindow):
    """Branded startup window shown before the main window is constructed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StartupSplashWindow")
        self.setWindowTitle("Fluor4CellPower")
        self.setWindowIcon(QIcon(AppIconPath))
        self.resize(720, 360)
        self.setFixedSize(720, 360)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fadeAnimation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fadeAnimation.setDuration(220)
        self._fadeAnimation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fadeAnimation.finished.connect(self.close)

        root = QFrame(self)
        root.setObjectName("StartupSplashRoot")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.imageLabel = QLabel(root)
        self.imageLabel.setObjectName("StartupSplashImage")
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageLabel.setScaledContents(False)

        self.titleLabel = QLabel("Fluor4CellPower", root)
        self.titleLabel.setObjectName("StartupSplashTitle")
        self.subTitleLabel = QLabel("正在初始化上位机界面与设备模块…", root)
        self.subTitleLabel.setObjectName("StartupSplashSubtitle")
        self.progressBar = ProgressBar(root)
        self.progressBar.setRange(0, 0)
        self.progressBar.setFixedHeight(4)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 18)
        layout.setSpacing(0)
        layout.addWidget(self.imageLabel, 1)
        layout.addSpacing(12)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.subTitleLabel)
        layout.addSpacing(12)
        layout.addWidget(self.progressBar)

        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.addWidget(root)

        self._loadBackground()
        self._applyStyle()
        self._centerOnScreen()

    def _loadBackground(self) -> None:
        image_path = CTX.dirs.AssetsDir / "F4CP_2x1_1200x600.png"
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.imageLabel.setText("F4CP")
            return
        target = QSize(720, 270)
        self.imageLabel.setPixmap(pixmap.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def _applyStyle(self) -> None:
        dark = isDarkTheme()
        root_bg = "#181A20" if dark else "#FFFFFF"
        title = "#FFFFFF" if dark else "#111827"
        subtitle = "rgba(255,255,255,0.68)" if dark else "rgba(15,23,42,0.62)"
        border = "rgba(255,255,255,0.12)" if dark else "rgba(15,23,42,0.10)"
        self.setStyleSheet(f"""
            QFrame#StartupSplashRoot {{
                background: {root_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QLabel#StartupSplashImage {{
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
                background: #0B0F18;
            }}
            QLabel#StartupSplashTitle {{
                color: {title};
                font-size: 24px;
                font-weight: 700;
                padding-left: 24px;
                padding-right: 24px;
            }}
            QLabel#StartupSplashSubtitle {{
                color: {subtitle};
                font-size: 13px;
                padding-left: 24px;
                padding-right: 24px;
                padding-top: 4px;
            }}
            ProgressBar {{
                margin-left: 24px;
                margin-right: 24px;
            }}
        """)

    def _centerOnScreen(self) -> None:
        desktop = QApplication.desktop().availableGeometry()
        self.move(desktop.center().x() - self.width() // 2, desktop.center().y() - self.height() // 2)

    def setText(self, text: str) -> None:
        self.subTitleLabel.setText(text)
        QApplication.processEvents()

    def finish(self, mainWindow=None) -> None:
        self.raise_()
        self._fadeAnimation.stop()
        self._fadeAnimation.setStartValue(self._opacity.opacity())
        self._fadeAnimation.setEndValue(0.0)
        self._fadeAnimation.start()


class DynamicIsland(QFrame):
    _LEVEL_COLOR = {
        "success": "#35C759",
        "warning": "#FFB020",
        "error": "#FF453A",
        "info": "#4C8DFF",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DynamicIsland")
        self.setFixedHeight(34)
        self.setMinimumWidth(188)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._dark = isDarkTheme()
        self._level = "info"
        self._hiding = False
        self._duration = 3200
        self._hideTimer = QTimer(self)
        self._hideTimer.setSingleShot(True)
        self._hideTimer.timeout.connect(self._hideAnimated)

        self._opacityEffect = QGraphicsOpacityEffect(self)
        self._opacityEffect.setOpacity(0)
        self.setGraphicsEffect(self._opacityEffect)

        self._fadeAnimation = QPropertyAnimation(self._opacityEffect, b"opacity", self)
        self._fadeAnimation.setDuration(160)
        self._fadeAnimation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fadeAnimation.finished.connect(self._onFadeFinished)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self.indicator = QLabel(self)
        self.indicator.setObjectName("DynamicIslandIndicator")
        self.indicator.setFixedSize(8, 8)

        self.titleLabel = QLabel(self)
        self.titleLabel.setObjectName("DynamicIslandTitle")
        self.titleLabel.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        self.contentLabel = QLabel(self)
        self.contentLabel.setObjectName("DynamicIslandContent")
        self.contentLabel.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        layout.addWidget(self.indicator)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.contentLabel)

        self._applyStyle("info")
        self.hide()

    def notify(self, title: str, content: str = "", level: str = "info", duration: int = 3200):
        title = (title or "通知").strip()
        content = (content or "").strip()
        level = (level or "info").lower()

        self._level = level
        self._hiding = False
        self._applyStyle(level)
        self.titleLabel.setText(self._elide(title, 150))
        self.contentLabel.setText(self._elide(content, 240))
        self.contentLabel.setVisible(bool(content))

        self.setFixedWidth(self._targetWidth(title, content))
        self.recenter()
        self.raise_()
        self.show()

        self._fadeAnimation.stop()
        self._fadeAnimation.setStartValue(self._opacityEffect.opacity())
        self._fadeAnimation.setEndValue(1)
        self._fadeAnimation.start()

        self._duration = max(1000, int(duration or 3200))
        self._hideTimer.start(self._duration)

    def setDarkTheme(self, dark: bool):
        self._dark = dark
        self._applyStyle()

    def recenter(self):
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(0, (parent.width() - self.width()) // 2)
        y = max(4, (parent.height() - self.height()) // 2)
        self.move(x, y)

    def _targetWidth(self, title: str, content: str) -> int:
        parent = self.parentWidget()
        maxWidth = 520
        if parent is not None:
            maxWidth = max(188, min(maxWidth, parent.width() - 220))
        titleWidth = self.titleLabel.fontMetrics().horizontalAdvance(title or "通知")
        contentWidth = self.contentLabel.fontMetrics().horizontalAdvance(content or "")
        width = 54 + min(titleWidth, 150) + (min(contentWidth, 240) + 8 if content else 0)
        return max(188, min(maxWidth, width))

    def _elide(self, text: str, maxWidth: int) -> str:
        return self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, maxWidth)

    def _hideAnimated(self):
        self._hiding = True
        self._fadeAnimation.stop()
        self._fadeAnimation.setStartValue(self._opacityEffect.opacity())
        self._fadeAnimation.setEndValue(0)
        self._fadeAnimation.start()

    def _onFadeFinished(self):
        if self._hiding and self._opacityEffect.opacity() <= 0:
            self.hide()
            self._hiding = False

    def _applyStyle(self, level: str = None):
        color = self._LEVEL_COLOR.get((level or self._level).lower(), self._LEVEL_COLOR["info"])
        bg = "rgba(34, 34, 34, 232)" if self._dark else "rgba(250, 250, 250, 238)"
        border = "rgba(255, 255, 255, 36)" if self._dark else "rgba(0, 0, 0, 18)"
        titleColor = "#FFFFFF" if self._dark else "#171717"
        contentColor = "rgba(255, 255, 255, 170)" if self._dark else "rgba(0, 0, 0, 150)"
        self.setStyleSheet(f"""
            QFrame#DynamicIsland {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 17px;
            }}
            QLabel#DynamicIslandIndicator {{
                background: {color};
                border-radius: 4px;
            }}
            QLabel#DynamicIslandTitle {{
                color: {titleColor};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#DynamicIslandContent {{
                color: {contentColor};
                font-size: 12px;
            }}
        """)


class Window(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("Window")
        # self.updateFrameless()
        self.homeInterface = HomePage(self)
        self.deviceInterface = DevicePage(self)
        self.powerInterface = PowerPage(self)
        self.daplinkInterface = DaplinkPage(self)
        self.settingInterface = SettingsPage(self)

        self.__initNavigation()
        self.__initWindow()
        self._onThemeChanged()
        cfg.themeChanged.connect(self._onThemeChanged)

        StyleSheet.HOME_PAGE.apply(self.homeInterface)
        StyleSheet.DEVICE_PAGE.apply(self.deviceInterface)
        StyleSheet.SETTINGS_PAGE.apply(self.settingInterface)
        StyleSheet.DAPLINK_PAGE.apply(self.daplinkInterface)

        QTimer.singleShot(150, self._checkUpdateOnStartUp)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.dynamicIsland.recenter()

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
            self.daplinkInterface, UF4Icon.FLASH_SETTINGS,
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
        self.resize(1400, 1100)
        self.setWindowIcon(QIcon(AppIconPath))
        self.setWindowTitle("UF4 POWER")
        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.dynamicIsland = DynamicIsland(self.titleBar)
        self.dynamicIsland.recenter()
        self.dynamicIsland.raise_()
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def close(self):
        logger.warning("Application closed")
        super().close()

    def closeEvent(self, event: QCloseEvent):
        self.powerInterface.shutdown()
        super().closeEvent(event)

    def _onThemeChanged(self, *_):
        dark = isDarkTheme()
        bgColor = "#242424" if dark else "#F3F3F3"
        self.setStyleSheet(f"Window {{ background: transparent;}}")
        self.setCustomBackgroundColor(QColor("#F3F3F3"), QColor("#242424"))

        # if hasattr(self, "dynamicIsland"):
        self.dynamicIsland.setDarkTheme(dark)
        # if hasattr(self, "powerInterface") and self.powerInterface is not None:
            # self.powerInterface._refreshThemeBundle()

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
        app = QApplication(sys.argv)
        setTheme(cfg.themeMode.value)
        w = Window()
        w.show()
        w.setMicaEffectEnabled(True)

        app.exec_()
    except Exception as e:
        logger.error(e)
