# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: splashscreen.py
#  @FileType: 启动页组件文件，负责应用加载时的品牌展示
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

from PyQt5.QtCore import QEventLoop, QSize, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget

from qfluentwidgets import SplashScreen


class F4SplashScreen(SplashScreen):
    """带标准标题栏的启动页。

    默认情况下 qfluentwidgets 的 SplashScreen 不显示标题栏图标和标题，
    这里统一替换为 qframelesswindow.StandardTitleBar。
    """

    def __init__(
        self,
        icon: QIcon | str | None = None,
        parent: QWidget | None = None,
        title: str | None = None,
        icon_size: QSize | None = None,
    ) -> None:
        resolved_icon = self._resolve_icon(icon, parent)
        super().__init__(resolved_icon, parent)
        self.setIconSize(icon_size or QSize(102, 102))

    @staticmethod
    def _resolve_icon(icon: QIcon | str | None, parent: QWidget | None) -> QIcon:
        if isinstance(icon, QIcon):
            return icon

        if isinstance(icon, str) and icon.strip():
            return QIcon(icon)

        if parent is not None and not parent.windowIcon().isNull():
            return parent.windowIcon()

        app = QApplication.instance()
        if app is not None and not app.windowIcon().isNull():
            return app.windowIcon()

        return QIcon()

    def syncWindowMeta(self, icon: QIcon | None = None, title: str | None = None) -> None:
        """同步标题栏图标和标题。"""
        resolved_icon = icon or self.windowIcon()
        resolved_title = title if title is not None else self._fallback_title()

        if not resolved_icon.isNull():
            self.setIcon(resolved_icon)
            self._titleBar.setIcon(resolved_icon)

        self._titleBar.setTitle(resolved_title)

    def _fallback_title(self) -> str:
        parent = self.parentWidget()
        if parent is not None:
            parent_title = parent.windowTitle().strip()
            if parent_title:
                return parent_title

        title = self.windowTitle().strip()
        if title:
            return title

        app = QApplication.instance()
        if app is not None:
            return app.applicationName().strip()

        return ""

    def showFor(self, duration: int = 0) -> None:
        """显示启动页，必要时在指定时长后自动关闭。"""
        self.show()

        if duration > 0:
            QTimer.singleShot(duration, self.finish)

    def wait(self, duration: int = 3000) -> None:
        """阻塞事件循环一段时间，适合演示或串行初始化。"""
        loop = QEventLoop(self)
        QTimer.singleShot(max(0, duration), loop.quit)
        loop.exec()


def createSplashScreen(
    parent: QWidget,
    icon: QIcon | str | None = None,
    title: str | None = None,
    icon_size: QSize | None = None,
    show_immediately: bool = True,
) -> F4SplashScreen:
    """为主窗口创建启动页。"""
    splash = F4SplashScreen(icon=icon, parent=parent, title=title, icon_size=icon_size)
    if show_immediately:
        splash.show()
    return splash
