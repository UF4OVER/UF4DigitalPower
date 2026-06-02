# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_page_device_connection_modes.py
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

from PyQt5.QtWidgets import QApplication

from widgets.pages import DevicePage


class DevicePageConnectionModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_connection_mode_controls_switch_between_serial_and_bluetooth(self):
        page = DevicePage()
        try:
            page.modeCombo.setCurrentIndex(1)
            self.assertEqual(page.connectionTypeCombo.currentText(), "串口")
            self.assertFalse(page.portCombo.isHidden())
            self.assertTrue(page.bluetoothCombo.isHidden())
            self.assertFalse(page.cmdSpin.isHidden())

            page.connectionTypeCombo.setCurrentText("蓝牙")

            self.assertTrue(page.portCombo.isHidden())
            self.assertTrue(page.baudCombo.isHidden())
            self.assertFalse(page.bluetoothCombo.isHidden())
            self.assertFalse(page.cmdSpin.isHidden())
        finally:
            page.deleteLater()

    def test_bluetooth_target_keeps_display_name_and_address_mapping(self):
        page = DevicePage()
        try:
            page._addBluetoothTarget("F4CP-BLE", "11:22:33:44:55:66")

            self.assertEqual(page.bluetoothCombo.currentText(), "F4CP-BLE (11:22:33:44:55:66)")
            self.assertEqual(
                page._bluetoothDevices["F4CP-BLE (11:22:33:44:55:66)"],
                "11:22:33:44:55:66",
            )
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
