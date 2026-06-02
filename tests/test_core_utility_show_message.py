# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_core_utility_show_message.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import os
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import app.core.utility as utility
from app.core.utility import showMessage


class UtilityShowMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_calls_success_infobar(self):
        parent = QWidget()
        utility._INFOBAR_MANAGER_CONFIGURED = False
        manager = MagicMock()

        with patch("app.core.utility.InfoBarManager.make", return_value=manager) as make_mock:
            with patch("app.core.utility.InfoBar.success") as success_mock:
                showMessage(parent, "Done", "Operation OK", "success", autoCloseMs=1200)

        make_mock.assert_called_once()
        self.assertEqual(manager.margin, 24)
        self.assertEqual(manager.spacing, 12)
        success_mock.assert_called_once_with(
            "Done",
            "Operation OK",
            duration=1200,
            position=utility.InfoBarPosition.TOP_RIGHT,
            parent=parent,
        )

    def test_calls_warning_infobar(self):
        parent = QWidget()
        utility._INFOBAR_MANAGER_CONFIGURED = True

        with patch("app.core.utility.InfoBar.warning") as warning_mock:
            showMessage(parent, "Warn", "Need attention", "warning")

        warning_mock.assert_called_once()

    def test_unknown_level_falls_back_to_info(self):
        parent = QWidget()
        utility._INFOBAR_MANAGER_CONFIGURED = True

        with patch("app.core.utility.InfoBar.info") as info_mock:
            showMessage(parent, "Hint", "Default info", "other")

        info_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()

