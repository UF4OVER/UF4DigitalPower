# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026/5/12
#  @FileName: manager_notification.py
#  @Software: PyCharm
#  @System  : Windows 11 25H2
#  @Author  : UF4
#  @Contact :
#  @Python  :
# -------------------------------
"""Side-slide notification manager.

Usage
-----
Call ``bindNotificationWindow(window)`` once after the main window is created.
After that, use ``notificationManager().showCard(...)`` from anywhere in the
application without any additional per-widget wiring.

Design notes
------------
* A single ``NotificationPanel`` (transparent, frame-less overlay) is
  parented directly to the main window. It stacks cards in the
  bottom-right corner and slides each one in/out with a
  ``QPropertyAnimation`` on the ``pos`` property.
* The panel installs a lightweight ``QObject`` event-filter on the parent
  window so it can reposition itself on every ``Resize`` / ``Move`` event –
  no global event loop hooks or per-widget signal bindings are required.
* ``notificationManager()`` returns the process-wide singleton without
  needing a global import.
"""

from __future__ import annotations

import weakref
from typing import Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter, QPainterPath
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from qfluentwidgets import (
    FluentIcon as FIF,
    TransparentToolButton,
    isDarkTheme,
)

__all__ = [
    "bindNotificationWindow",
    "notificationManager",
    "NotificationManager",
    "NotificationCard",
]

# ---------------------------------------------------------------------------
# Module-level singleton reference
# ---------------------------------------------------------------------------
_MANAGER_REF: Optional[weakref.ref] = None  # weakref to the active NotificationManager


def notificationManager() -> Optional["NotificationManager"]:
    """Return the process-wide :class:`NotificationManager` if one has been
    bound, otherwise return *None*."""
    if _MANAGER_REF is not None:
        return _MANAGER_REF()
    return None


def bindNotificationWindow(window: QWidget) -> "NotificationManager":
    """Bind a :class:`NotificationManager` to *window* and return it.

    Call this exactly once, typically right after the main window is shown.
    The manager is attached as a child of *window* so it follows its
    lifetime automatically.
    """
    global _MANAGER_REF
    manager = NotificationManager(window)
    _MANAGER_REF = weakref.ref(manager)
    return manager


# ---------------------------------------------------------------------------
# Card constants
# ---------------------------------------------------------------------------
_CARD_WIDTH = 320
_CARD_MIN_HEIGHT = 72
_CARD_MARGIN = 10        # gap between stacked cards
_PANEL_RIGHT_MARGIN = 16
_PANEL_BOTTOM_MARGIN = 16
_SLIDE_IN_MS = 260
_SLIDE_OUT_MS = 220
_DEFAULT_DURATION_MS = 4000

_LEVEL_COLORS: dict[str, tuple[str, str]] = {
    # (dark bg, light bg)
    "info":    ("#1E3A5F", "#EFF6FF"),
    "success": ("#14532D", "#F0FDF4"),
    "warning": ("#713F12", "#FFFBEB"),
    "error":   ("#7F1D1D", "#FEF2F2"),
}
_LEVEL_ACCENT: dict[str, str] = {
    "info":    "#3B82F6",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error":   "#EF4444",
}


# ---------------------------------------------------------------------------
# NotificationCard
# ---------------------------------------------------------------------------
class NotificationCard(QWidget):
    """A single notification card that slides in from the right."""

    confirmed = pyqtSignal(object)
    closed = pyqtSignal(object)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        level: str = "info",
        auto_recycle: bool = True,
        duration: int = _DEFAULT_DURATION_MS,
        confirm_text: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._level = level
        self._autoRecycle = auto_recycle
        self._duration = duration
        self._closing = False

        self.setFixedWidth(_CARD_WIDTH)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)

        self._buildUi(title, subtitle, confirm_text)

        if auto_recycle and duration > 0:
            self._autoTimer = QTimer(self)
            self._autoTimer.setSingleShot(True)
            self._autoTimer.timeout.connect(self._onAutoClose)
            self._autoTimer.start(duration)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _buildUi(self, title: str, subtitle: str, confirm_text: str):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._container = QWidget(self)
        self._container.setObjectName("notifCard")
        outer.addWidget(self._container)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(4)

        # Title row: accent bar + title + close button
        headerRow = QHBoxLayout()
        headerRow.setSpacing(8)

        self._accentBar = QWidget(self._container)
        self._accentBar.setFixedWidth(3)
        self._accentBar.setMinimumHeight(20)
        headerRow.addWidget(self._accentBar, 0, Qt.AlignVCenter)

        self._titleLabel = QLabel(title, self._container)
        self._titleLabel.setWordWrap(False)
        headerRow.addWidget(self._titleLabel, 1)

        self._closeBtn = TransparentToolButton(FIF.CLOSE, self._container)
        self._closeBtn.setFixedSize(28, 28)
        self._closeBtn.clicked.connect(self._onCloseClicked)
        headerRow.addWidget(self._closeBtn, 0)

        layout.addLayout(headerRow)

        if subtitle:
            self._subtitleLabel = QLabel(subtitle, self._container)
            self._subtitleLabel.setWordWrap(True)
            self._subtitleLabel.setObjectName("notifSubtitle")
            layout.addWidget(self._subtitleLabel)
        else:
            self._subtitleLabel = None

        if confirm_text:
            from qfluentwidgets import PushButton
            btnRow = QHBoxLayout()
            btnRow.addStretch(1)
            self._confirmBtn = PushButton(confirm_text, self._container)
            self._confirmBtn.setFixedHeight(28)
            self._confirmBtn.clicked.connect(self._onConfirmClicked)
            btnRow.addWidget(self._confirmBtn)
            layout.addLayout(btnRow)
        else:
            self._confirmBtn = None

        self._applyTheme()
        self.adjustSize()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _applyTheme(self):
        dark = isDarkTheme()
        bgPair = _LEVEL_COLORS.get(self._level, _LEVEL_COLORS["info"])
        bg = bgPair[0] if dark else bgPair[1]
        accent = _LEVEL_ACCENT.get(self._level, _LEVEL_ACCENT["info"])
        textColor = "#E8EEF4" if dark else "#1E293B"
        subColor = "#94A3B8" if dark else "#64748B"
        borderColor = "rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.08)"

        self._container.setStyleSheet(
            f"""
            QWidget#notifCard {{
                background: {bg};
                border: 1px solid {borderColor};
                border-radius: 10px;
            }}
            """
        )
        self._accentBar.setStyleSheet(
            f"background: {accent}; border-radius: 1px;"
        )
        self._titleLabel.setStyleSheet(
            f"color: {textColor}; font-weight: 600; font-size: 13px;"
        )
        if self._subtitleLabel:
            self._subtitleLabel.setStyleSheet(
                f"color: {subColor}; font-size: 12px;"
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _onCloseClicked(self):
        self.closed.emit(self)
        manager = notificationManager()
        if manager:
            manager.closeCard(self)

    def _onConfirmClicked(self):
        self.confirmed.emit(self)
        manager = notificationManager()
        if manager:
            manager.closeCard(self)

    def _onAutoClose(self):
        manager = notificationManager()
        if manager:
            manager.closeCard(self)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        # Let the child container's stylesheet draw itself; the outer
        # widget stays transparent so the rounded corners show cleanly.
        super().paintEvent(event)


# ---------------------------------------------------------------------------
# _WindowResizeFilter – event filter that repositions the panel
# ---------------------------------------------------------------------------
class _WindowResizeFilter(QObject):
    """Listens for Resize/Show events on the host window and notifies the
    panel so it can reposition itself."""

    def __init__(self, panel: "NotificationPanel", parent: QObject | None = None):
        super().__init__(parent)
        self._panel = panel

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.Move):
            self._panel._repositionPanel()
        return False  # never consume events


# ---------------------------------------------------------------------------
# NotificationPanel – transparent overlay widget
# ---------------------------------------------------------------------------
class NotificationPanel(QWidget):
    """Transparent, frameless overlay that hosts stacked notification cards.

    The panel is parented to the main window and covers its entire area.
    It is always kept on top via ``raise_()`` after repositioning.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)

        self._cards: list[NotificationCard] = []
        self._closing: set[NotificationCard] = set()

        # Install resize filter on the parent window
        self._resizeFilter = _WindowResizeFilter(self, parent)
        parent.installEventFilter(self._resizeFilter)

        self._repositionPanel()
        self.raise_()

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def _repositionPanel(self):
        if self.parent() is None:
            return
        parentRect: QRect = self.parent().rect()  # type: ignore[union-attr]
        self.setGeometry(parentRect)
        self.raise_()
        self._layoutCards()

    def _cardX(self) -> int:
        return self.width() - _CARD_WIDTH - _PANEL_RIGHT_MARGIN

    def _offscreenX(self) -> int:
        """X coordinate just off the right edge (for slide-in/out)."""
        return self.width() + 8

    def _layoutCards(self):
        """Update positions of all visible cards without animation."""
        x = self._cardX()
        bottom = self.height() - _PANEL_BOTTOM_MARGIN
        for card in reversed(self._cards):
            if card in self._closing:
                continue
            y = bottom - card.height()
            card.move(x, y)
            bottom = y - _CARD_MARGIN

    # ------------------------------------------------------------------
    # Public API (called by NotificationManager)
    # ------------------------------------------------------------------
    def addCard(self, card: NotificationCard):
        card.setParent(self)
        card.adjustSize()
        card.show()

        # New card always appears at the bottom-right corner
        startX = self._offscreenX()
        endX = self._cardX()
        endY = self.height() - _PANEL_BOTTOM_MARGIN - card.height()

        card.move(startX, endY)

        # Push existing cards upward first, then append the new card
        self._animatePush(card)
        self._cards.append(card)

        # Slide the new card in
        anim = QPropertyAnimation(card, b"pos", self)
        anim.setDuration(_SLIDE_IN_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(QPoint(startX, endY))
        anim.setEndValue(QPoint(endX, endY))
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def _animatePush(self, newCard: NotificationCard):
        """Slide existing cards upward to make room for the new bottom card."""
        x = self._cardX()
        # Start above where the new card will sit
        bottom = self.height() - _PANEL_BOTTOM_MARGIN - newCard.height() - _CARD_MARGIN

        visibleCards = [c for c in self._cards if c not in self._closing]
        for card in reversed(visibleCards):
            bottom -= card.height()
            anim = QPropertyAnimation(card, b"pos", self)
            anim.setDuration(_SLIDE_IN_MS)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.setEndValue(QPoint(x, bottom))
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            bottom -= _CARD_MARGIN

    def removeCard(self, card: NotificationCard):
        if card not in self._cards or card in self._closing:
            return
        self._closing.add(card)

        # Fade + slide out to the right
        effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(effect)

        fadeAnim = QPropertyAnimation(effect, b"opacity", self)
        fadeAnim.setDuration(_SLIDE_OUT_MS)
        fadeAnim.setStartValue(1.0)
        fadeAnim.setEndValue(0.0)

        slideAnim = QPropertyAnimation(card, b"pos", self)
        slideAnim.setDuration(_SLIDE_OUT_MS)
        slideAnim.setEasingCurve(QEasingCurve.InCubic)
        slideAnim.setEndValue(QPoint(self._offscreenX(), card.y()))

        group = QSequentialAnimationGroup(self)
        group.addAnimation(slideAnim)
        group.finished.connect(lambda: self._finishRemoval(card))
        group.start(QSequentialAnimationGroup.DeleteWhenStopped)

        # Also run fade independently
        fadeAnim.start(QPropertyAnimation.DeleteWhenStopped)

    def _finishRemoval(self, card: NotificationCard):
        self._closing.discard(card)
        if card in self._cards:
            self._cards.remove(card)
        card.hide()
        card.setParent(None)
        card.deleteLater()
        # Restack remaining cards
        QTimer.singleShot(0, self._layoutCards)

    def clearAll(self):
        for card in list(self._cards):
            self.removeCard(card)

    # ------------------------------------------------------------------
    # Mouse transparency for areas without cards
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        # Fully transparent – nothing to paint
        pass


# ---------------------------------------------------------------------------
# NotificationManager
# ---------------------------------------------------------------------------
class NotificationManager(QObject):
    """High-level manager that exposes a simple ``showCard`` / ``closeCard``
    API to the rest of the application.

    Parameters
    ----------
    window:
        The top-level QWidget to attach the notification panel to.
    """

    def __init__(self, window: QWidget):
        super().__init__(window)
        self._panel = NotificationPanel(window)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def cards(self) -> list[NotificationCard]:
        """Read-only view of the currently visible cards."""
        return list(self._panel._cards)

    def showCard(
        self,
        title: str,
        subtitle: str = "",
        level: str = "info",
        auto_recycle: bool = True,
        duration: int = _DEFAULT_DURATION_MS,
        confirm_text: str = "",
    ) -> NotificationCard:
        """Create and display a new notification card.

        Parameters
        ----------
        title:
            Bold heading text shown on the card.
        subtitle:
            Optional smaller body text below the heading.
        level:
            Severity level – one of ``"info"``, ``"success"``,
            ``"warning"``, or ``"error"``.
        auto_recycle:
            Whether the card should close itself after *duration* ms.
        duration:
            Auto-close delay in milliseconds (only used when
            *auto_recycle* is ``True``).
        confirm_text:
            If non-empty, a confirmation button with this label is
            shown; clicking it emits ``NotificationCard.confirmed``.

        Returns
        -------
        NotificationCard
            The newly created card so callers can connect signals.
        """
        card = NotificationCard(
            title=title,
            subtitle=subtitle,
            level=level,
            auto_recycle=auto_recycle,
            duration=duration,
            confirm_text=confirm_text,
        )
        self._panel.addCard(card)
        return card

    def closeCard(self, card: NotificationCard):
        """Animate *card* out and destroy it."""
        self._panel.removeCard(card)

    def clear(self):
        """Close and destroy all currently visible cards."""
        self._panel.clearAll()
