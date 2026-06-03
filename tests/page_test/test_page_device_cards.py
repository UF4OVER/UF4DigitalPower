# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_page_device_cards.py
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

from PySide6.QtWidgets import QApplication
from qfluentwidgets import CardWidget

from app.widgets.pages.page_device import DevicePage


class DevicePageCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_serial_sections_use_qfluent_cards(self):
        page = DevicePage()

        try:
            for card in (
                page.connectionCard,
                page.sendCard,
                page.tlvCard,
                page.consoleCard,
            ):
                self.assertIsInstance(card, CardWidget)
                self.assertEqual(card.objectName(), "PageCard")
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
