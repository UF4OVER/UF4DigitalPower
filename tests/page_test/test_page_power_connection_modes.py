# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_page_power_connection_modes.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication

from widgets.pages import PowerPage


class _FakeScanner(QObject):
    device_connected = pyqtSignal(object)
    device_disconnected = pyqtSignal()

    def __init__(self, vid: int, pid: int, parent=None):
        super().__init__(parent)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class PowerPageConnectionModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_connection_mode_controls_switch_between_serial_and_bluetooth(self):
        with patch("app.pages.page_power.DeviceScanner", _FakeScanner):
            page = PowerPage()

        try:
            self.assertEqual(page.connectionTypeCombo.currentText(), "串口")
            self.assertFalse(page.portCombo.isHidden())
            self.assertFalse(page.baudCombo.isHidden())
            self.assertTrue(page.bluetoothCombo.isHidden())

            page.connectionTypeCombo.setCurrentText("蓝牙")

            self.assertTrue(page.portCombo.isHidden())
            self.assertTrue(page.baudCombo.isHidden())
            self.assertFalse(page.bluetoothCombo.isHidden())
        finally:
            page.shutdown()
            page.deleteLater()

    def test_bluetooth_target_keeps_display_name_and_address_mapping(self):
        with patch("app.pages.page_power.DeviceScanner", _FakeScanner):
            page = PowerPage()

        try:
            page._addBluetoothTarget("F4CP-Power", "AA:BB:CC:DD:EE:FF")

            self.assertEqual(page.bluetoothCombo.currentText(), "F4CP-Power (AA:BB:CC:DD:EE:FF)")
            self.assertEqual(
                page._bluetoothDevices["F4CP-Power (AA:BB:CC:DD:EE:FF)"],
                "AA:BB:CC:DD:EE:FF",
            )
        finally:
            page.shutdown()
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
