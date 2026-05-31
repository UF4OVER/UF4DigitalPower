# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/30
#  @FileName: dynamic_island.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)

from qfluentwidgets import isDarkTheme


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

        self._applyFonts()
        self._applyStyle("info")
        self.hide()

    def notify(self, title: str, content: str = "", level: str = "info", duration: int = 3200):
        title = (title or "通知").strip()
        content = (content or "").strip()
        level = (level or "info").lower()

        self._applyFonts()
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
            }}
            QLabel#DynamicIslandContent {{
                color: {contentColor};
            }}
        """)

    def _applyFonts(self):
        app = QApplication.instance()
        base_font = app.font() if app is not None else self.font()

        island_font = QFont(base_font)
        island_font.setPointSize(10)
        self.setFont(island_font)

        title_font = QFont(island_font)
        title_font.setWeight(QFont.DemiBold)
        self.titleLabel.setFont(title_font)

        content_font = QFont(island_font)
        self.contentLabel.setFont(content_font)

