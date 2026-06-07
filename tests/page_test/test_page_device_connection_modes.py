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

from app.core.const import PowerCommand, PowerDataType
from app.protocol.tvlcom import build_frame, encode_tlv
from app.widgets.pages import DevicePage


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

    def test_tvlcom_payload_uses_power_protocol_empty_read_tlv(self):
        page = DevicePage()
        try:
            page._addDefaultTlvRow()

            self.assertEqual(
                page._buildV2PayloadFromTable(),
                encode_tlv(PowerDataType.SET_VOLTAGE_LIMIT),
            )
        finally:
            page.deleteLater()

    def test_tvlcom_payload_and_parser_share_power_frame_codec(self):
        page = DevicePage()
        try:
            page._addDefaultTlvRow()
            page.tlvTable.item(0, 2).setText("8000")
            payload = page._buildV2PayloadFromTable()
            self.assertEqual(
                payload,
                encode_tlv(PowerDataType.SET_VOLTAGE_LIMIT, (8000).to_bytes(4, "little")),
            )

            logs = []
            page.rxEventSignal.connect(logs.append)
            page._initV2Protocol()
            page._handleV2RxFrames(build_frame(PowerCommand.ACK, 3, payload))

            self.assertEqual(len(logs), 1)
            self.assertIn("V2 ACK cmd=00 seq=3", logs[0])
            self.assertIn("SET_VOLTAGE_LIMIT", logs[0])
            self.assertIn("8000", logs[0])
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
