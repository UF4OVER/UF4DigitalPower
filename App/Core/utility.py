# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/4/25
#  @FileName: utility.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------
from typing import Optional

from PyQt5.QtCore import QEasingCurve, QObject, QPoint, QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from qfluentwidgets import FluentIcon, IconWidget, InfoBar, InfoBarIcon, InfoBarPosition, PrimaryPushButton, isDarkTheme


class SideNotificationCard(QFrame):
    """右侧通知卡片。DEBUG 版本：结构直接、变量直观、方便改样式。"""

    def __init__(self, title: str, content: str, icon=None, autoCloseMs: int = 5000, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.manager = None
        self.autoCloseMs = autoCloseMs
        self.closedByUser = False

        self.setObjectName("SideNotificationCard")
        self.setFixedWidth(380)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.iconWidget = IconWidget(self)
        self.iconWidget.setFixedSize(26, 26)
        self.setIcon(icon)

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setObjectName("SideNotificationTitle")
        self.titleLabel.setWordWrap(True)

        self.contentLabel = QLabel(content, self)
        self.contentLabel.setObjectName("SideNotificationContent")
        self.contentLabel.setWordWrap(True)

        self.confirmButton = PrimaryPushButton("确认", self)
        self.confirmButton.setFixedWidth(72)
        self.confirmButton.clicked.connect(self.closeNotification)

        textLayout = QVBoxLayout()
        textLayout.setContentsMargins(0, 0, 0, 0)
        textLayout.setSpacing(4)
        textLayout.addWidget(self.titleLabel)
        textLayout.addWidget(self.contentLabel)

        topLayout = QHBoxLayout()
        topLayout.setContentsMargins(0, 0, 0, 0)
        topLayout.setSpacing(12)
        topLayout.addWidget(self.iconWidget, 0, Qt.AlignmentFlag.AlignTop)
        topLayout.addLayout(textLayout, 1)

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(16, 14, 16, 14)
        mainLayout.setSpacing(12)
        mainLayout.addLayout(topLayout)
        mainLayout.addWidget(self.confirmButton, 0, Qt.AlignmentFlag.AlignRight)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.closeNotification)

        self.applyTheme()

    def setIcon(self, icon):
        if icon is None:
            icon = FluentIcon.INFO

        if isinstance(icon, QIcon):
            self.iconWidget.setIcon(icon)
        else:
            self.iconWidget.setIcon(icon)

    def applyTheme(self):
        if isDarkTheme():
            bg = "rgba(45, 45, 45, 245)"
            border = "rgba(255, 255, 255, 28)"
            title = "#FFFFFF"
            content = "#C8C8C8"
            shadow = Qt.GlobalColor.black
        else:
            bg = "rgba(255, 255, 255, 248)"
            border = "rgba(0, 0, 0, 22)"
            title = "#1F1F1F"
            content = "#606060"
            shadow = Qt.GlobalColor.gray

        self.setStyleSheet(f"""
            QFrame#SideNotificationCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel#SideNotificationTitle {{
                color: {title};
                font-size: 15px;
                font-weight: 600;
            }}
            QLabel#SideNotificationContent {{
                color: {content};
                font-size: 13px;
            }}
        """)

        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(32)
        effect.setOffset(0, 6)
        effect.setColor(shadow)
        self.setGraphicsEffect(effect)

    def startAutoClose(self):
        if self.autoCloseMs is not None and self.autoCloseMs > 0:
            self.timer.start(self.autoCloseMs)

    def closeNotification(self):
        if self.manager is not None:
            self.manager.remove(self)
        else:
            self.close()
            self.deleteLater()


class NotificationManager(QObject):
    """右侧通知管理器：负责弹出、位置更新、关闭、自动上移。"""

    def __init__(self, parentWindow: QWidget, cardWidth: int = 380, marginRight: int = 24, marginBottom: int = 24, spacing: int = 14):
        super().__init__(parentWindow)
        self.parentWindow = parentWindow
        self.cardWidth = cardWidth
        self.marginRight = marginRight
        self.marginBottom = marginBottom
        self.spacing = spacing
        self.cards = []

        oldResizeEvent = parentWindow.resizeEvent

        def resizeEvent(event):
            oldResizeEvent(event)
            self.updatePositions(animated=False)

        parentWindow.resizeEvent = resizeEvent

    def show(self, title: str, content: str, level: str = "info", icon=None, autoCloseMs: int = 5000):
        cardIcon = self._resolveIcon(level, icon)
        card = SideNotificationCard(title, content, cardIcon, autoCloseMs, self.parentWindow)
        card.manager = self
        card.setFixedWidth(self.cardWidth)
        card.adjustSize()

        self.cards.append(card)

        startX = self.parentWindow.width() + 20
        endX = self.parentWindow.width() - self.marginRight - self.cardWidth
        endY = self._targetY(card)

        card.move(startX, endY)
        card.show()
        card.raise_()

        self._animateMove(card, QPoint(endX, endY))
        self.updatePositions(exceptCard=card)
        card.startAutoClose()
        return card

    def remove(self, card: SideNotificationCard):
        if card not in self.cards:
            return

        self.cards.remove(card)
        target = QPoint(self.parentWindow.width() + 20, card.y())
        self._animateMove(card, target, finished=lambda: self._deleteCard(card))
        self.updatePositions()

    def clear(self):
        for card in self.cards[:]:
            self.remove(card)

    def updatePositions(self, animated: bool = True, exceptCard: Optional[SideNotificationCard] = None):
        y = self.parentWindow.height() - self.marginBottom
        x = self.parentWindow.width() - self.marginRight - self.cardWidth

        for card in self.cards:
            y -= card.height()
            target = QPoint(x, y)
            if card is not exceptCard:
                if animated:
                    self._animateMove(card, target)
                else:
                    card.move(target)
            y -= self.spacing

    def _targetY(self, card: SideNotificationCard):
        y = self.parentWindow.height() - self.marginBottom
        for item in self.cards:
            y -= item.height()
            if item is card:
                return y
            y -= self.spacing
        return y

    def _animateMove(self, widget: QWidget, target: QPoint, finished=None):
        from PyQt5.QtCore import QPropertyAnimation

        animation = QPropertyAnimation(widget, b"pos", widget)
        animation.setDuration(220)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(widget.pos())
        animation.setEndValue(target)

        widget._moveAnimation = animation
        if finished is not None:
            animation.finished.connect(finished)
        animation.start()

    def _deleteCard(self, card: SideNotificationCard):
        card.close()
        card.deleteLater()

    def _resolveIcon(self, level: str, icon):
        if icon is not None:
            return icon
        if level == "success":
            return InfoBarIcon.SUCCESS
        if level == "warning":
            return InfoBarIcon.WARNING
        if level == "error":
            return InfoBarIcon.ERROR
        return InfoBarIcon.INFORMATION


def bindNotificationWindow(parentWindow: QWidget) -> NotificationManager:
    """绑定全局侧边通知管理器。入口 Window 初始化时调用一次。"""
    manager = NotificationManager(parentWindow)
    parentWindow.notificationManager = manager
    return manager


def showSideMessage(parent, title: str, content: str, level: str = "info", icon=None, autoCloseMs: int = 5000):
    """全局侧边通知调用。优先使用侧边卡片，没有管理器时回退 InfoBar。"""
    window = parent.window() if parent is not None else None
    manager = getattr(window, "notificationManager", None)

    if manager is None:
        return showMessage(parent, title, content, level)

    return manager.show(
        title=title,
        content=content,
        level=level,
        icon=icon,
        autoCloseMs=autoCloseMs,
    )


def showMessage(parent, title: str, content: str, level: str = "info", useSide: bool = False, autoCloseMs: int = 5000):
    if useSide:
        window = parent.window() if parent is not None else None
        manager = getattr(window, "notificationManager", None)
        if manager is not None:
            return manager.show(title, content, level=level, autoCloseMs=autoCloseMs)

    kwargs = dict(
        title=title,
        content=content,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=3000,
        parent=parent,
    )

    if level == "success":
        return InfoBar.success(**kwargs)
    elif level == "warning":
        return InfoBar.warning(**kwargs)
    elif level == "error":
        return InfoBar.error(**kwargs)
    else:
        return InfoBar.info(**kwargs)
