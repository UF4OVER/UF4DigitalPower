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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app.widgets.pages import PowerPage
from app.session import PowerStatus


class _FakeSession:
    is_open = True

    def __init__(self):
        self.cfg = SimpleNamespace(port="COM_TEST")

    def set_event_receiver(self, _receiver) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


def _disconnect_protocol_slots(page: PowerPage) -> None:
    for signal in (
        page.outputLimitsRequested,
        page.protectionValuesRequested,
        page.powerStateRequested,
    ):
        try:
            signal.disconnect()
        except TypeError:
            pass


def _build_status(
    power_state: int,
    *,
    set_voltage_limit_mv: int = 5000,
    set_current_limit_ma: int = 1000,
    ovp_set_value_mv: int = 44000,
    ocp_set_value_ma: int = 10500,
    otp_set_value_mc: int = 80000,
    fan_set_value: int = 0,
) -> PowerStatus:
    return PowerStatus(
        vin_mv=24000,
        iin_ma=1000,
        vout_mv=0,
        iout_ma=0,
        core_temp_mc=35000,
        board_temp_mc=32000,
        temp2_temp_mc=33000,
        set_voltage_limit_mv=set_voltage_limit_mv,
        set_current_limit_ma=set_current_limit_ma,
        cc_cv_mode=1,
        power_state=power_state,
        fault_state=0,
        state_machine_flag_bits=0b0010,
        state_machine_state=0,
        otp_value_mc=32000,
        otp_set_value_mc=otp_set_value_mc,
        ovp_value_mv=0,
        ovp_set_value_mv=ovp_set_value_mv,
        ocp_value_ma=0,
        ocp_set_value_ma=ocp_set_value_ma,
        duty_cmd_permille=0,
        pwm_a_compare=0,
        pwm_d_compare=0,
        fan_speed=0,
        fan_set_value=fan_set_value,
    )


class PowerPageOutputStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_poll_refresh_does_not_overwrite_staged_output_state(self):
        page = PowerPage()

        try:
            _disconnect_protocol_slots(page)
            page._client._session = _FakeSession()
            emitted = []
            page.outputLimitsRequested.connect(
                lambda voltage_mv, current_ma, enabled: emitted.append(
                    (voltage_mv, current_ma, enabled)
                )
            )

            offline_status = _build_status(power_state=0)
            page._updateStatusView(offline_status)

            page.parameterEditor.outputSwitch.setChecked(True)
            self.assertTrue(page.parameterEditor.outputSwitch.isChecked())
            self.assertTrue(page._stagedOutputEnabled)

            page._updateStatusView(offline_status)
            self.assertTrue(page.parameterEditor.outputSwitch.isChecked())
            self.assertTrue(page._stagedOutputEnabled)

            page.parameterEditor.outputVoltage.setValue(5.0)
            page.parameterEditor.outputCurrent.setValue(1.0)
            page._applyOutputLimits()

            self.assertEqual(emitted, [(5000, 1000, True)])

            online_status = _build_status(power_state=1)
            page._updateStatusView(online_status)
            self.assertIsNone(page._stagedOutputEnabled)
            self.assertTrue(page.parameterEditor.outputSwitch.isChecked())
        finally:
            page.shutdown()
            page.deleteLater()

    def test_status_refresh_does_not_overwrite_dirty_output_values_before_apply(self):
        page = PowerPage()

        try:
            _disconnect_protocol_slots(page)
            page._client._session = _FakeSession()
            emitted = []
            page.outputLimitsRequested.connect(
                lambda voltage_mv, current_ma, enabled: emitted.append(
                    (voltage_mv, current_ma, enabled)
                )
            )

            old_status = _build_status(power_state=1, set_voltage_limit_mv=5000, set_current_limit_ma=1000)
            page._updateStatusView(old_status)

            page.parameterEditor.outputVoltage.setValue(8.0)
            page.parameterEditor.outputCurrent.setValue(1.2)
            page._updateStatusView(old_status)

            self.assertEqual(page.parameterEditor.outputVoltage.value(), 8.0)
            self.assertEqual(page.parameterEditor.outputCurrent.value(), 1.2)

            page._applyOutputLimits()

            self.assertEqual(emitted, [(8000, 1200, True)])
        finally:
            page.shutdown()
            page.deleteLater()

    def test_pending_output_values_clear_only_after_matching_readback(self):
        page = PowerPage()

        try:
            _disconnect_protocol_slots(page)
            page._client._session = _FakeSession()
            old_status = _build_status(power_state=1, set_voltage_limit_mv=5000, set_current_limit_ma=1000)
            page._updateStatusView(old_status)

            page.parameterEditor.outputVoltage.setValue(8.0)
            page.parameterEditor.outputCurrent.setValue(1.2)
            page._applyOutputLimits()

            page._updateStatusView(old_status)
            self.assertEqual(page.parameterEditor.outputVoltage.value(), 8.0)
            self.assertEqual(page.parameterEditor.outputCurrent.value(), 1.2)
            self.assertEqual(page._pendingOutputSettings, (8000, 1200))

            matching_status = _build_status(power_state=1, set_voltage_limit_mv=8000, set_current_limit_ma=1200)
            page._updateStatusView(matching_status)
            self.assertIsNone(page._pendingOutputSettings)

            later_status = _build_status(power_state=1, set_voltage_limit_mv=9000, set_current_limit_ma=1300)
            page._updateStatusView(later_status)
            self.assertEqual(page.parameterEditor.outputVoltage.value(), 9.0)
            self.assertEqual(page.parameterEditor.outputCurrent.value(), 1.3)
        finally:
            page.shutdown()
            page.deleteLater()

    def test_status_refresh_does_not_overwrite_dirty_protection_values_before_apply(self):
        page = PowerPage()

        try:
            _disconnect_protocol_slots(page)
            page._client._session = _FakeSession()
            emitted = []
            page.protectionValuesRequested.connect(
                lambda ovp_mv, ocp_ma, otp_mc, fan_value: emitted.append(
                    (ovp_mv, ocp_ma, otp_mc, fan_value)
                )
            )

            old_status = _build_status(
                power_state=1,
                ovp_set_value_mv=44000,
                ocp_set_value_ma=10500,
                otp_set_value_mc=85000,
                fan_set_value=700,
            )
            page._updateStatusView(old_status)

            page.parameterEditor.ovp.setValue(36.0)
            page.parameterEditor.ocp.setValue(2.5)
            page.parameterEditor.otp.setValue(75.0)
            page.parameterEditor.fan.setValue(500)
            page._updateStatusView(old_status)

            self.assertEqual(page.parameterEditor.ovp.value(), 36.0)
            self.assertEqual(page.parameterEditor.ocp.value(), 2.5)
            self.assertEqual(page.parameterEditor.otp.value(), 75.0)
            self.assertEqual(page.parameterEditor.fan.value(), 500)

            page._applyProtectionValues()

            self.assertEqual(emitted, [(36000, 2500, 75000, 500)])
        finally:
            page.shutdown()
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
