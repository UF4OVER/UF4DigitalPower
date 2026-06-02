# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_manager_notification.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from manager import (
    NotificationCard,
    bindNotificationWindow,
    notificationManager,
)


class NotificationManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        cls._window = QWidget()
        cls._window.resize(800, 600)
        cls._manager = bindNotificationWindow(cls._window)

    def test_notificationManagerReturnsSingleton(self):
        self.assertIs(notificationManager(), self._manager)

    def test_showCardReturnsNotificationCard(self):
        card = self._manager.showCard("Test", "subtitle", "info", auto_recycle=False)
        self.assertIsInstance(card, NotificationCard)
        self._manager.closeCard(card)

    def test_showCardAppearsInCardsList(self):
        before = len(self._manager.cards)
        card = self._manager.showCard("Test", level="success", auto_recycle=False)
        self.assertEqual(len(self._manager.cards), before + 1)
        self._manager.closeCard(card)

    def test_panelWidthStaysNarrowerThanWindow(self):
        window = QWidget()
        window.resize(800, 600)
        manager = bindNotificationWindow(window)
        window.show()
        self._app.processEvents()

        panel = manager._panel
        self.assertFalse(panel.isVisible())
        self.assertEqual(panel.width(), 0)

        card = manager.showCard("width check", auto_recycle=False)
        self._app.processEvents()
        self.assertTrue(panel.isVisible())
        self.assertLess(panel.width(), window.width())
        manager.closeCard(card)

    def test_allLevelsAccepted(self):
        for level in ("info", "success", "warning", "error"):
            card = self._manager.showCard("Title", level=level, auto_recycle=False)
            self.assertIsInstance(card, NotificationCard)
            self._manager.closeCard(card)

    def test_clearRemovesAllCards(self):
        for _ in range(3):
            self._manager.showCard("Bulk", auto_recycle=False)
        before = len(self._manager.cards)
        self.assertGreater(before, 0)
        self._manager.clear()
        self._app.processEvents()
        # All cards should be queued for removal (in _closing set on the panel)
        panel = self._manager._panel
        self.assertTrue(
            all(c in panel._closing for c in panel._cards),
            "After clear(), every remaining card should be in the _closing set",
        )

    def test_confirmedSignalEmitted(self):
        received = []
        card = self._manager.showCard(
            "Confirm me", confirm_text="OK", auto_recycle=False
        )
        card.confirmed.connect(lambda c: received.append(c))
        card._onConfirmClicked()
        self._app.processEvents()
        self.assertEqual(received, [card])

    def test_closedSignalEmitted(self):
        received = []
        card = self._manager.showCard("Close me", auto_recycle=False)
        card.closed.connect(lambda c: received.append(c))
        card._onCloseClicked()
        self._app.processEvents()
        self.assertEqual(received, [card])


if __name__ == "__main__":
    unittest.main()
