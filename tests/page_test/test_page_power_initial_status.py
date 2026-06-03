# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_page_power_initial_status.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.widgets.pages.page_power import PowerPage


class PowerPageInitialStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_status_card_is_populated_before_device_reports(self):
        page = PowerPage()

        try:
            self.assertEqual(page.statusFields["output"].valueLabel.text(), "关闭")
            self.assertEqual(page.statusFields["fault"].valueLabel.text(), "无")
            self.assertEqual(page.statusFields["core_temp"].valueLabel.text(), "0.00 °C")
            self.assertEqual(page.statusFields["pwm"].valueLabel.text(), "0 / 0")
            self.assertEqual(page.statusGrid.columnCount(), 3)
            self.assertEqual(page.metricCards["vin"].valueLabel.text(), "0.000")
            self.assertEqual(page.parameterEditor.outputVoltage.value(), 0.0)
            self.assertEqual(page.parameterEditor.ovp.value(), 44.0)
            self.assertIsNone(page._lastStatus)
            self.assertEqual(page.logEdit.toPlainText(), "")
        finally:
            page.shutdown()
            page.deleteLater()

    def test_parameter_spinboxes_emit_protocol_units(self):
        page = PowerPage()

        try:
            page._client._session = SimpleNamespace(is_open=True)
            page._setWriteControlsEnabled(True)
            page.parameterEditor.outputVoltage.setValue(12.345)
            page.parameterEditor.outputCurrent.setValue(1.234)
            page.parameterEditor.ovp.setValue(44.0)
            page.parameterEditor.ocp.setValue(10.5)
            page.parameterEditor.otp.setValue(85.0)
            page.parameterEditor.fan.setValue(700)

            output = []
            protection = []
            page.outputLimitsRequested.connect(lambda *args: output.append(args))
            page.protectionValuesRequested.connect(lambda *args: protection.append(args))

            page._applyOutputLimits()
            page._setWriteControlsEnabled(True)
            page._applyProtectionValues()

            self.assertEqual(output, [(12345, 1234, False)])
            self.assertEqual(protection, [(44000, 10500, 85000, 700)])
        finally:
            page.shutdown()
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
