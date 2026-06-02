# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_session_powert_polling.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import time
import unittest
from types import SimpleNamespace
from typing import cast

from PyQt5.QtCore import QCoreApplication

from session import (
    F4CPPowerClient,
    PowerDataType,
    PowerStatus,
)
from session.session_power import (
    DEFAULT_STATUS_VALUES,
    STREAM_CHANNEL_SEPARATOR,
    STREAM_FAST_PERIOD_MS,
    STREAM_FAST_TYPES,
    STREAM_SLOW_PERIOD_MS,
    STREAM_SLOW_TYPES,
    STATUS_TYPES,
    decode_stream_sample,
    pack_stream_start_request,
    stream_sample_size,
)
from session.session_serial import SerialSession


DEFAULT_TEST_STATUS_VALUES = dict(DEFAULT_STATUS_VALUES)


def _pack_stream_group(types: tuple[PowerDataType, ...], base_value: int) -> bytes:
    sample = bytearray()
    for index, type_id in enumerate(types):
        value = base_value + index
        sample.extend(value.to_bytes(2, "little", signed=False))
        if index < len(types) - 1:
            sample.extend(STREAM_CHANNEL_SEPARATOR)
    return bytes(sample)


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
        self.stream_start_calls = []
        self.stream_stop_calls = []

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

    def start_streaming(self, interval_ms: int = 800, types=STREAM_FAST_TYPES, timeout_ms: int = 1000) -> None:
        selected = tuple(types)
        self.stream_start_calls.append((interval_ms, selected, timeout_ms))
        self._stream_types = selected
        self._stream_fast_types = selected
        self._stream_slow_types = STREAM_SLOW_TYPES
        self._stream_fast_sample_size = stream_sample_size(selected)
        self._stream_slow_sample_size = stream_sample_size(STREAM_SLOW_TYPES)
        self._stream_slow_every_fast_samples = STREAM_SLOW_PERIOD_MS // STREAM_FAST_PERIOD_MS
        self._stream_fast_samples_until_slow = 0
        self._stream_enabled = True
        self._poll_requested_interval_ms = max(200, int(interval_ms))

    def stop_streaming(self, timeout_ms: int = 1000) -> None:
        self.stream_stop_calls.append(timeout_ms)
        self._stop_raw_stream_state()


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

        self.assertTrue(client._stream_enabled)
        self.assertEqual(client.stream_start_calls[0][0], 250)
        self.assertEqual(client.read_status_calls, [])

        client.stop_polling()
        self.assertFalse(client._stream_enabled)
        self.assertEqual(client.stream_stop_calls, [1000])

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
        self.assertEqual(timeout_ms, 2000)
        self.assertEqual(int.from_bytes(values[PowerDataType.SET_VOLTAGE_LIMIT], "little"), 12000)
        self.assertEqual(int.from_bytes(values[PowerDataType.SET_CURRENT_LIMIT], "little"), 3500)
        self.assertEqual(int.from_bytes(values[PowerDataType.POWER_STATE], "little"), 1)
        self.assertEqual(len(written), 1)
        self.assertEqual(client.read_status_calls, [2000])
        self.assertEqual(errors, [])

    def test_output_write_pauses_and_resumes_active_polling(self):
        client = _TestPowerClient()
        client.attach_session(cast(SerialSession, _FakeSerialSession()))

        logs = []
        client.log.connect(logs.append)

        client.start_polling(250)
        self._process_events()
        client.read_status_calls.clear()

        client.request_set_output_limits(12000, 3500, True)

        self.assertFalse(client._poll_timer.isActive())
        self.assertTrue(client._poll_resume_timer.isActive())
        self.assertEqual(len(client.write_calls), 1)
        self.assertEqual(client.stream_stop_calls, [1000])
        self.assertEqual(client.read_status_calls, [2000])
        self.assertIn("Raw stream paused for write", logs)

        self._process_events(0.95)

        self.assertTrue(client._stream_enabled)
        self.assertEqual(client.stream_start_calls[-1][0], 250)

    def test_output_write_resumes_when_poll_timer_was_temporarily_inactive(self):
        client = _TestPowerClient()
        client.attach_session(cast(SerialSession, _FakeSerialSession()))

        client.start_polling(250)
        self._process_events()
        client._poll_timer.stop()
        client.read_status_calls.clear()

        client.request_set_output_limits(12000, 3500, True)

        self.assertTrue(client._poll_resume_timer.isActive())

        self._process_events(0.95)

        self.assertTrue(client._stream_enabled)
        self.assertEqual(client.stream_start_calls[-1][0], 250)

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
        self.assertEqual(client.read_status_calls, [2000, 2000])
        self.assertEqual(errors, [])

    def test_raw_stream_sample_uses_separator_between_channel_values(self):
        types = (
            PowerDataType.OUTPUT_VOLTAGE,
            PowerDataType.OUTPUT_CURRENT,
            PowerDataType.CORE_TEMPERATURE,
        )
        sample = (
            (12000).to_bytes(2, "little")
            + STREAM_CHANNEL_SEPARATOR
            + (500).to_bytes(2, "little")
            + STREAM_CHANNEL_SEPARATOR
            + (35000).to_bytes(2, "little")
        )

        self.assertEqual(stream_sample_size(types), len(sample))
        self.assertEqual(
            decode_stream_sample(sample, types),
            {
                PowerDataType.OUTPUT_VOLTAGE: 12000,
                PowerDataType.OUTPUT_CURRENT: 500,
                PowerDataType.CORE_TEMPERATURE: 35000,
            },
        )

    def test_stream_start_request_contains_fast_and_slow_groups(self):
        payload = pack_stream_start_request(
            STREAM_FAST_TYPES,
            STREAM_FAST_PERIOD_MS,
            STREAM_SLOW_TYPES,
            STREAM_SLOW_PERIOD_MS,
        )

        fast_tlv_len = len(STREAM_FAST_TYPES) * 3
        self.assertEqual(int.from_bytes(payload[0:2], "little"), 20)
        self.assertEqual(payload[2], len(STREAM_FAST_TYPES))
        self.assertEqual(payload[3:3 + fast_tlv_len], b"".join(bytes([int(t), 0, 0]) for t in STREAM_FAST_TYPES))
        slow_offset = 3 + fast_tlv_len
        self.assertEqual(int.from_bytes(payload[slow_offset:slow_offset + 2], "little"), 1000)
        self.assertEqual(payload[slow_offset + 2], len(STREAM_SLOW_TYPES))
        self.assertEqual(
            payload[slow_offset + 3:],
            b"".join(bytes([int(t), 0, 0]) for t in STREAM_SLOW_TYPES),
        )

    def test_raw_stream_schedule_parses_slow_group_once_per_second(self):
        client = F4CPPowerClient()
        client._last_values.update(DEFAULT_TEST_STATUS_VALUES)
        client._stream_enabled = True
        client._stream_fast_types = STREAM_FAST_TYPES
        client._stream_slow_types = STREAM_SLOW_TYPES
        client._stream_fast_sample_size = stream_sample_size(STREAM_FAST_TYPES)
        client._stream_slow_sample_size = stream_sample_size(STREAM_SLOW_TYPES)
        client._stream_slow_every_fast_samples = 50
        client._stream_fast_samples_until_slow = 0

        first = _pack_stream_group(STREAM_FAST_TYPES, 12000) + _pack_stream_group(STREAM_SLOW_TYPES, 32000)
        second = _pack_stream_group(STREAM_FAST_TYPES, 12100)
        client._buffer.extend(first + second)

        first_values = client._extract_raw_stream_values()
        second_values = client._extract_raw_stream_values()

        self.assertIn(PowerDataType.CORE_TEMPERATURE, first_values)
        self.assertNotIn(PowerDataType.CORE_TEMPERATURE, second_values)
        self.assertEqual(client._stream_fast_samples_until_slow, 48)


if __name__ == "__main__":
    unittest.main()

