# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_page_power_output_staging.py
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
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication

from widgets.pages import PowerPage
from session import PowerStatus


class _FakeScanner(QObject):
    device_connected = pyqtSignal(object)
    device_disconnected = pyqtSignal()

    def __init__(self, vid: int, pid: int, parent=None):
        super().__init__(parent)
        self.vid = vid
        self.pid = pid
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


def _build_status(power_state: int) -> PowerStatus:
    return PowerStatus(
        vin_mv=24000,
        iin_ma=1000,
        vout_mv=0,
        iout_ma=0,
        core_temp_mc=35000,
        board_temp_mc=32000,
        set_voltage_limit_mv=5000,
        set_current_limit_ma=1000,
        cc_cv_mode=1,
        power_state=power_state,
        fault_state=0,
        state_machine_flag_bits=0b0010,
        state_machine_state=0,
        otp_value_mc=32000,
        otp_set_value_mc=80000,
        ovp_value_mv=0,
        ovp_set_value_mv=44000,
        ocp_value_ma=0,
        ocp_set_value_ma=10500,
        duty_cmd_permille=0,
        pwm_a_compare=0,
        pwm_d_compare=0,
        fan_speed=0,
        fan_set_value=0,
    )


class PowerPageOutputStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_poll_refresh_does_not_overwrite_staged_output_state(self):
        with patch("app.pages.page_power.DeviceScanner", _FakeScanner):
            page = PowerPage()

        try:
            page._client._session = SimpleNamespace(is_open=True)
            emitted = []
            page.outputLimitsRequested.connect(
                lambda voltage_mv, current_ma, enabled: emitted.append(
                    (voltage_mv, current_ma, enabled)
                )
            )

            offline_status = _build_status(power_state=0)
            page._updateStatusView(offline_status)

            page.outputSwitch.setChecked(True)
            self.assertTrue(page.outputSwitch.isChecked())
            self.assertTrue(page._stagedOutputEnabled)

            page._updateStatusView(offline_status)
            self.assertTrue(page.outputSwitch.isChecked())
            self.assertTrue(page._stagedOutputEnabled)

            page.writeParams["set_voltage"].editor.setText("5.000")
            page.writeParams["set_current"].editor.setText("1.000")
            page._applyOutputLimits()

            self.assertEqual(emitted, [(5000, 1000, True)])

            online_status = _build_status(power_state=1)
            page._updateStatusView(online_status)
            self.assertIsNone(page._stagedOutputEnabled)
            self.assertTrue(page.outputSwitch.isChecked())
        finally:
            page.shutdown()
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()