from collections import deque
from typing import Optional, Sequence, Type

from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QTimer,
    Qt,
    pyqtProperty,
    pyqtSignal
)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import TransparentToolButton

from app import (
    NotificationType,
    NotificationColorMapBase,
    NotificationIconMapBase,
    resolve_notification_colors,
    resolve_notification_icon,
)


class ThemeCard(QWidget):
    requestClose = pyqtSignal(object)
    folded = pyqtSignal(object)
    shiftFinished = pyqtSignal(object)

    RIGHT_PIX = 40
    BOTTOM_PIX = 3
    BORDER_RADIUS = 6
    CARD_SIZE = (420, 88)

    ICON_SIZE = 18

    def __init__(
        self,
        parent=None,
        n_type: NotificationType = NotificationType.Information,
        title: str = "",
        sub: str = "",
        duration_ms: int = 2600,
        color_enums: Optional[Sequence[Type[NotificationColorMapBase]]] = None,
        icon_enums: Optional[Sequence[Type[NotificationIconMapBase]]] = None,
    ):
        super().__init__(parent)
        self._type = n_type
        self._title = title or n_type.name
        self._sub = sub or ""
        self._duration_ms = max(500, duration_ms)
        self._color_enums = tuple(color_enums or ())
        self._icon_enums = tuple(icon_enums or ())

        self._is_shifting = False
        self._is_folding = False
        self._pending_fold = False

        self.setFixedSize(*self.CARD_SIZE)
        self._init_widget()
        self._init_anim()

    def _init_widget(self):
        theme_color, back_color = resolve_notification_colors(self._type, *self._color_enums)

        self.setObjectName("themeBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#themeBar {{ background-color: {theme_color}; border-radius: {self.BORDER_RADIUS}px; }}"
        )

        self._background_bar = QLabel(self)
        self._background_bar.setObjectName("backgroundBar")
        self._background_bar.setAttribute(Qt.WA_Hover, True)
        self._background_bar.installEventFilter(self)
        self._normal_color = QColor(back_color)
        self._hover_color = self._normal_color.lighter(110)
        self._current_color = self._normal_color

        self._icon_label = QLabel(self)
        self._icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        fluent_icon = resolve_notification_icon(self._type, *self._icon_enums)
        self._icon_label.setPixmap(fluent_icon.icon().pixmap(self.ICON_SIZE, self.ICON_SIZE))

        self._title_label = QLabel(self._title, self._background_bar)
        self._title_label.setStyleSheet("font: 600 14px 'Microsoft YaHei'; color: #1f2937; background: transparent;")

        self._sub_label = QLabel(self._sub, self._background_bar)
        self._sub_label.setStyleSheet("font: 12px 'Microsoft YaHei'; color: #475467; background: transparent;")

        self._close_btn = TransparentToolButton(self)
        self._close_btn.setFixedWidth(self.RIGHT_PIX)
        self._close_btn.setIcon(resolve_notification_icon(NotificationType.Error, *self._icon_enums))
        self._close_btn.clicked.connect(lambda: self.requestClose.emit(self))

        self._update_bg(self._normal_color)

    def _init_anim(self):
        self._color_anim = QPropertyAnimation(self, b"bgColor", self)
        self._color_anim.setDuration(220)
        self._color_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(220)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._slide_anim.finished.connect(self._on_slide_finished)

        self._life_timer = QTimer(self)
        self._life_timer.setSingleShot(True)
        self._life_timer.timeout.connect(self._on_timeout)

    @pyqtProperty(QColor)
    def bgColor(self):
        return self._current_color

    @bgColor.setter
    def bgColor(self, color):
        self._current_color = color
        self._update_bg(color)

    def _update_bg(self, color: QColor):
        self._background_bar.setStyleSheet(
            f"QLabel#backgroundBar {{ background-color: {color.name()}; border-radius: {self.BORDER_RADIUS}px; }}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        bg_w = w - self.RIGHT_PIX
        bg_h = h - self.BOTTOM_PIX
        self._background_bar.setGeometry(self.RIGHT_PIX, 0, bg_w, bg_h)

        icon_x = max(0, (self.RIGHT_PIX - self.ICON_SIZE) // 2)
        icon_y = max(0, (bg_h - self.ICON_SIZE) // 2)
        self._icon_label.setGeometry(icon_x, icon_y, self.ICON_SIZE, self.ICON_SIZE)

        # Keep the left strip for icon, and place text in the main content area.
        text_left = 18
        text_right = 12
        text_w = max(40, bg_w - text_left - text_right)
        self._title_label.setGeometry(text_left, 14, text_w, 22)
        self._sub_label.setGeometry(text_left, 40, text_w, 24)
        self._close_btn.setGeometry(w - self.RIGHT_PIX, 0, self.RIGHT_PIX, bg_h)

    def eventFilter(self, obj, event):
        if obj is self._background_bar:
            if event.type() == QEvent.Enter:
                self._start_color_anim(self._hover_color)
            elif event.type() == QEvent.Leave:
                self._start_color_anim(self._normal_color)
        return super().eventFilter(obj, event)

    def _start_color_anim(self, target: QColor):
        self._color_anim.stop()
        self._color_anim.setStartValue(getattr(self, "_current_color", self._normal_color))
        self._color_anim.setEndValue(target)
        self._color_anim.start()

    def start_show(self, target_pos: QPoint):
        self.move(target_pos.x() + self.width() + 16, target_pos.y())
        self.show()
        self._slide_to(target_pos, shifting=False)

    def shift_to(self, target_pos: QPoint):
        if self._is_folding:
            return
        self._slide_to(target_pos, shifting=True)

    def request_fold(self):
        if self._is_folding:
            return
        if self._is_shifting:
            self._pending_fold = True
            return
        self._start_fold()

    def _slide_to(self, target_pos: QPoint, shifting: bool):
        self._slide_anim.stop()
        self._is_shifting = shifting
        self._slide_anim.setStartValue(self.pos())
        self._slide_anim.setEndValue(target_pos)
        self._slide_anim.start()

    def _on_timeout(self):
        self.request_fold()

    def _on_slide_finished(self):
        if self._is_folding:
            self.folded.emit(self)
            return

        if self._is_shifting:
            self._is_shifting = False
            self.shiftFinished.emit(self)
            if self._pending_fold:
                self._pending_fold = False
                self._start_fold()
            return

        if not self._life_timer.isActive():
            self._life_timer.start(self._duration_ms)

    def _start_fold(self):
        if self._is_folding:
            return
        self._is_folding = True
        self._life_timer.stop()
        self._slide_anim.stop()

        target = QPoint(self.pos().x() + self.width() + 16, self.pos().y())
        self._slide_anim.setStartValue(self.pos())
        self._slide_anim.setEndValue(target)
        self._slide_anim.start()


class PopupManager(QObject):
    def __init__(
        self,
        host: QWidget,
        max_visible: int = 5,
        spacing: int = 10,
        top_margin: int = 16,
        right_margin: int = 16,
        color_enums: Optional[Sequence[Type[NotificationColorMapBase]]] = None,
        icon_enums: Optional[Sequence[Type[NotificationIconMapBase]]] = None,
    ):
        super().__init__(host)
        self._host = host
        self._max_visible = max(1, max_visible)
        self._spacing = spacing
        self._top_margin = top_margin
        self._right_margin = right_margin
        self._color_enums = tuple(color_enums or ())
        self._icon_enums = tuple(icon_enums or ())

        self._pending = deque()
        self._active = []

        self._host.installEventFilter(self)

    def push(self, n_type: NotificationType, title: str, sub: str = "", duration_ms: int = 2600):
        self._pending.append((n_type, title, sub, duration_ms))
        self._promote_pending()

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Resize:
            self._relayout(animate=False)
        return super().eventFilter(obj, event)

    def _promote_pending(self):
        while self._pending and len(self._active) < self._max_visible:
            card = self._create_card(*self._pending.popleft())
            self._active.append(card)
            card.start_show(self._target_pos(len(self._active) - 1))

    def _create_card(self, n_type: NotificationType, title: str, sub: str, duration_ms: int):
        card = ThemeCard(
            self._host,
            n_type=n_type,
            title=title,
            sub=sub,
            duration_ms=duration_ms,
            color_enums=self._color_enums,
            icon_enums=self._icon_enums,
        )
        card.requestClose.connect(lambda c=card: c.request_fold())
        card.folded.connect(self._on_folded)
        card.shiftFinished.connect(self._on_shift_finished)
        return card

    def _on_folded(self, card: ThemeCard):
        if card in self._active:
            self._active.remove(card)
        card.hide()
        card.deleteLater()

        self._relayout(animate=True)
        QTimer.singleShot(0, self._promote_pending)

    def _on_shift_finished(self, _card: ThemeCard):
        pass

    def _relayout(self, animate: bool):
        for idx, card in enumerate(self._active):
            target = self._target_pos(idx)
            if animate:
                card.shift_to(target)
            else:
                card.move(target)

    def _target_pos(self, index: int) -> QPoint:
        sample_w, sample_h = ThemeCard.CARD_SIZE
        x = self._host.width() - sample_w - self._right_margin
        y = self._top_margin + index * (sample_h + self._spacing)
        return QPoint(max(0, x), y)


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Popup Queue Demo")
        self.resize(900, 560)

        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        add_btn = QPushButton("Push 5 Messages", central)
        add_btn.clicked.connect(self._push_batch)
        layout.addWidget(add_btn)

        stress_btn = QPushButton("Stress (timeout + shift)", central)
        stress_btn.clicked.connect(self._push_stress)
        layout.addWidget(stress_btn)

        layout.addStretch(1)

        self._manager = PopupManager(self, max_visible=3)

    def _push_batch(self):
        self._manager.push(NotificationType.Information, "System", "Device connected", 2100)
        self._manager.push(NotificationType.Success, "Upload", "Profile uploaded", 2300)
        self._manager.push(NotificationType.Warning, "Temperature", "Close to threshold", 1900)
        self._manager.push(NotificationType.Error, "COM", "Read timeout", 2400)
        self._manager.push(NotificationType.Debugging, "Debug", "Retry #2 queued", 1600)

    def _push_stress(self):
        self._manager.push(NotificationType.Information, "Queue", "A", 900)
        self._manager.push(NotificationType.Information, "Queue", "B", 900)
        self._manager.push(NotificationType.Information, "Queue", "C", 900)
        self._manager.push(NotificationType.Information, "Queue", "D", 900)


if __name__ == "__main__":
    import sys

    qt_app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(qt_app.exec_())
