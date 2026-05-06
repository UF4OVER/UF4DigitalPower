import time
import unittest
from types import SimpleNamespace
from typing import cast

from PyQt5.QtCore import QCoreApplication

from App.Core.Session.session_powert import (
    F4CPPowerClient,
    PowerDataType,
    PowerStatus,
)
from App.Core.Session.session_serial import SerialSession


class _FakeSerialSession:
    def __init__(self, port: str = "COM12"):
        self.is_open = True
        self.cfg = SimpleNamespace(port=port)
        self.event_receiver = None

    def set_event_receiver(self, receiver):
        self.event_receiver = receiver


class _TestPowerClient(F4CPPowerClient):
    def __init__(self):
        super().__init__()
        self.write_calls = []
        self.read_status_calls = []

    def write_values(self, values: dict[PowerDataType, bytes], timeout_ms: int = 1000) -> None:
        self.write_calls.append((dict(values), timeout_ms))

    def read_status(self, timeout_ms: int = 1000) -> PowerStatus:
        self.read_status_calls.append(timeout_ms)
        status = PowerStatus(
            vin_mv=24000,
            iin_ma=1000,
            vout_mv=12000,
            iout_ma=500,
            core_temp_mc=35000,
            board_temp_mc=32000,
            set_voltage_limit_mv=12000,
            set_current_limit_ma=3000,
            cc_cv_mode=0,
            power_state=1,
            fault_state=0,
            state_machine_flag_bits=0b1000,
            state_machine_state=1,
            otp_value_mc=32000,
            otp_set_value_mc=85000,
            ovp_value_mv=12000,
            ovp_set_value_mv=44000,
            ocp_value_ma=500,
            ocp_set_value_ma=3500,
            duty_cmd_permille=420,
            pwm_a_compare=15080,
            pwm_d_compare=1560,
            fan_speed=650,
            fan_set_value=700,
        )
        self._last_status = status
        self.statusUpdated.emit(status)
        return status


class PowerClientPollingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def _process_events(self, seconds: float = 0.05) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._app.processEvents()

    def test_start_polling_uses_host_timer_and_immediately_requests_status(self):
        client = _TestPowerClient()
        client.attach_session(cast(SerialSession, _FakeSerialSession()))

        logs = []
        client.log.connect(logs.append)

        client.start_polling(250)
        self._process_events()

        self.assertTrue(client._poll_timer.isActive())
        self.assertEqual(client._poll_timer.interval(), 250)
        self.assertGreaterEqual(len(client.read_status_calls), 1)
        self.assertIn("Host polling started (250 ms)", logs)

        client.stop_polling()
        self.assertFalse(client._poll_timer.isActive())

    def test_output_limit_write_refreshes_status_after_ack(self):
        client = _TestPowerClient()
        client.attach_session(cast(SerialSession, _FakeSerialSession()))

        written = []
        errors = []
        client.outputLimitsWritten.connect(lambda: written.append(True))
        client.error.connect(errors.append)

        client.request_set_output_limits(12000, 3500, True)

        self.assertEqual(len(client.write_calls), 1)
        values, timeout_ms = client.write_calls[0]
        self.assertEqual(timeout_ms, 1000)
        self.assertEqual(int.from_bytes(values[PowerDataType.SET_VOLTAGE_LIMIT], "little"), 12000)
        self.assertEqual(int.from_bytes(values[PowerDataType.SET_CURRENT_LIMIT], "little"), 3500)
        self.assertEqual(int.from_bytes(values[PowerDataType.POWER_STATE], "little"), 1)
        self.assertEqual(len(written), 1)
        self.assertEqual(client.read_status_calls, [1000])
        self.assertEqual(errors, [])

    def test_protection_write_and_power_state_write_both_trigger_readback(self):
        client = _TestPowerClient()
        client.attach_session(cast(SerialSession, _FakeSerialSession()))

        protection_written = []
        power_state_values = []
        errors = []
        client.protectionValuesWritten.connect(lambda: protection_written.append(True))
        client.powerStateWritten.connect(power_state_values.append)
        client.error.connect(errors.append)

        client.request_set_protection_values(44000, 3500, 85000, 700)
        client.request_set_power_state(False)

        self.assertEqual(len(client.write_calls), 2)
        protection_values, _ = client.write_calls[0]
        power_state_values_raw, _ = client.write_calls[1]

        self.assertEqual(int.from_bytes(protection_values[PowerDataType.OVP_SET_VALUE], "little"), 44000)
        self.assertEqual(int.from_bytes(protection_values[PowerDataType.OCP_SET_VALUE], "little"), 3500)
        self.assertEqual(int.from_bytes(protection_values[PowerDataType.OTP_SET_VALUE], "little"), 85000)
        self.assertEqual(int.from_bytes(protection_values[PowerDataType.FAN_SET_VALUE], "little"), 700)
        self.assertEqual(int.from_bytes(power_state_values_raw[PowerDataType.POWER_STATE], "little"), 0)
        self.assertEqual(len(protection_written), 1)
        self.assertEqual(power_state_values, [False])
        self.assertEqual(client.read_status_calls, [1000, 1000])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

