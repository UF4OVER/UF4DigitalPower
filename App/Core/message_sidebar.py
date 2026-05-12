# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @FileName: message_sidebar.py
#  @Software: PyCharm
#  @System  : Windows
#  @Author  : UF4
# -------------------------------
from typing import Callable, Optional, Union

from PyQt5.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from qfluentwidgets import FluentIcon, IconWidget, PrimaryPushButton, TransparentToolButton, isDarkTheme


class MessageCard(QFrame):
    """qfluentwidgets 风格的右侧消息卡片。"""

    clicked = pyqtSignal()
    closed = pyqtSignal(object)

    def __init__(
            self,
            title: Optional[str],
            text: str,
            msg_type: int = 1,
            icon: Union[FluentIcon, QIcon, str, None] = None,
            slot: Optional[Callable] = None,
            close_on_clicked: bool = True,
            fold_after: Optional[int] = None,
            parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.msg_type = msg_type
        self.fold_after = fold_after
        self.close_on_clicked = close_on_clicked
        self._closing = False

        self.setObjectName("MessageCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(380)

        self.iconWidget = IconWidget(self)
        self.iconWidget.setFixedSize(28, 28)
        self.iconWidget.setIcon(self._icon(icon, msg_type))

        self.titleLabel = QLabel(title or text, self)
        self.titleLabel.setObjectName("MessageTitle")
        self.titleLabel.setWordWrap(True)

        self.textLabel = QLabel(text, self)
        self.textLabel.setObjectName("MessageText")
        self.textLabel.setWordWrap(True)
        self.textLabel.setVisible(title is not None)

        self.closeButton = TransparentToolButton(FluentIcon.CLOSE, self)
        self.closeButton.setFixedSize(28, 28)
        self.closeButton.clicked.connect(self.closeLater)

        self.okButton = PrimaryPushButton("确认", self)
        self.okButton.setFixedWidth(72)
        self.okButton.clicked.connect(self._onConfirmClicked)

        textLayout = QVBoxLayout()
        textLayout.setContentsMargins(0, 0, 0, 0)
        textLayout.setSpacing(4)
        textLayout.addWidget(self.titleLabel)
        textLayout.addWidget(self.textLabel)

        headerLayout = QHBoxLayout()
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.setSpacing(12)
        headerLayout.addWidget(self.iconWidget, 0, Qt.AlignmentFlag.AlignTop)
        headerLayout.addLayout(textLayout, 1)
        headerLayout.addWidget(self.closeButton, 0, Qt.AlignmentFlag.AlignTop)

        bodyLayout = QVBoxLayout(self)
        bodyLayout.setContentsMargins(16, 14, 16, 14)
        bodyLayout.setSpacing(12)
        bodyLayout.addLayout(headerLayout)
        bodyLayout.addWidget(self.okButton, 0, Qt.AlignmentFlag.AlignRight)

        if slot is not None:
            self.clicked.connect(slot)

        self.autoCloseTimer = QTimer(self)
        self.autoCloseTimer.setSingleShot(True)
        self.autoCloseTimer.timeout.connect(self.closeLater)

        self._applyStyle()
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        if self.fold_after is not None and self.fold_after > 0:
            self.autoCloseTimer.start(self.fold_after)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            if self.close_on_clicked:
                self.closeLater()

    def closeLater(self):
        if self._closing:
            return
        self._closing = True
        self.closed.emit(self)

    def _onConfirmClicked(self):
        self.clicked.emit()
        self.closeLater()

    def _icon(self, icon, msg_type: int):
        if icon is not None:
            return icon
        if msg_type == 0:
            return FluentIcon.CANCEL
        if msg_type == 2:
            return FluentIcon.ACCEPT
        if msg_type == 3:
            return FluentIcon.INFO
        return FluentIcon.INFO

    def _applyStyle(self):
        if isDarkTheme():
            bg = "rgba(38, 38, 38, 245)"
            border = "rgba(255, 255, 255, 26)"
            title = "#FFFFFF"
            text = "#C8C8C8"
            shadow_color = Qt.GlobalColor.black
        else:
            bg = "rgba(255, 255, 255, 248)"
            border = "rgba(0, 0, 0, 24)"
            title = "#1F1F1F"
            text = "#606060"
            shadow_color = Qt.GlobalColor.gray

        self.setStyleSheet(f"""
            QFrame#MessageCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel#MessageTitle {{
                color: {title};
                font-size: 15px;
                font-weight: 600;
            }}
            QLabel#MessageText {{
                color: {text};
                font-size: 13px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(shadow_color)
        self.setGraphicsEffect(shadow)


class MessageSidebar(QWidget):
    """右侧消息栏管理器。

    行为类似 SIUI：
    - sendMessageBox：发送自定义卡片
    - send：发送普通消息
    - 自动回收
    - 移除后下方卡片自动上移
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MessageSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFixedWidth(420)

        self.spacing = 16
        self.marginRight = 24
        self.marginBottom = 24
        self.cards = []
        self.hide()

    def sendMessageBox(self, message_box: QWidget):
        message_box.setParent(self.parentWidget())
        message_box.setFixedWidth(380)
        self._appendCard(message_box)

    def send(self,
             text: str,
             title: str = None,
             msg_type: int = 1,
             icon: Union[FluentIcon, QIcon, str, None] = None,
             slot=None,
             close_on_clicked=True,
             fold_after: int = 5000):
        message_box = MessageCard(
            title=title,
            text=text,
            msg_type=msg_type,
            icon=icon,
            slot=slot,
            close_on_clicked=close_on_clicked,
            fold_after=fold_after,
            parent=self.parentWidget(),
        )
        self._appendCard(message_box)
        return message_box

    def removeCard(self, message_box: QWidget):
        if message_box not in self.cards:
            return

        self.cards.remove(message_box)
        end = QPoint(self.parentWidget().width() + 40, message_box.y())
        self._moveTo(message_box, end, finished=lambda: self._deleteCard(message_box))
        self.updatePositions()

    def clear(self):
        for card in self.cards[:]:
            self.removeCard(card)

    def updatePositions(self, animated: bool = True):
        parent = self.parentWidget()
        if parent is None:
            return

        x = parent.width() - self.marginRight - 380
        y = parent.height() - self.marginBottom

        for card in self.cards:
            y -= card.height()
            target = QPoint(x, y)
            if animated:
                self._moveTo(card, target)
            else:
                card.move(target)
            y -= self.spacing

    def resizeToParent(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.width() - self.width(), 0, self.width(), parent.height())
        self.updatePositions(animated=False)

    def _appendCard(self, message_box: QWidget):
        parent = self.parentWidget()
        if parent is None:
            return

        if hasattr(message_box, "closed"):
            message_box.closed.connect(self.removeCard)

        self.cards.append(message_box)
        message_box.adjustSize()

        start = QPoint(parent.width() + 40, parent.height() - self.marginBottom - message_box.height())
        message_box.move(start)
        message_box.show()
        message_box.raise_()

        self.updatePositions(animated=False)
        self._moveTo(message_box, message_box.pos())
        self.updatePositions(animated=True)

    def _moveTo(self, widget: QWidget, target: QPoint, finished=None):
        animation = QPropertyAnimation(widget, b"pos", widget)
        animation.setDuration(220)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(widget.pos())
        animation.setEndValue(target)
        widget._messageMoveAnimation = animation
        if finished is not None:
            animation.finished.connect(finished)
        animation.start()

    def _deleteCard(self, card: QWidget):
        card.close()
        card.deleteLater()


class RightMessageSidebar(MessageSidebar):
    """主窗口右侧消息层。"""
    pass
