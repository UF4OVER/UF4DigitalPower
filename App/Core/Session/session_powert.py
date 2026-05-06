# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Iterable

from PyQt5.QtCore import QCoreApplication, QEventLoop, QIODevice, QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtSerialPort import QSerialPort

from App.Core.Session import (
    ErrorEvent,
    RxEvent,
    SendEvent,
    SerialEventType,
    SerialSession,
    SerialState,
    StateEvent,
    TxEvent,
)


class PowerClientError(RuntimeError):
    """Base error for power client failures."""


class PowerClientTimeoutError(PowerClientError):
    """Raised when the device response times out."""


class PowerClientCrcError(PowerClientError):
    """Raised when an incoming frame fails CRC validation."""


class PowerClientProtocolError(PowerClientError):
    """Raised when the frame structure or response content is invalid."""


class PowerClientNackError(PowerClientError):
    """Raised when the device returns NACK."""


class PowerClientAccessError(PowerClientProtocolError):
    """Raised when a requested operation violates the data metadata."""


class PowerCommand(IntEnum):
    ACK = 0x00
    READ = 0x01
    WRITE = 0x02
    REPORT = 0x03
    NACK = 0xFF


class PowerDataType(IntEnum):
    INPUT_VOLTAGE = 10
    INPUT_CURRENT = 11
    OUTPUT_VOLTAGE = 12
    OUTPUT_CURRENT = 13
    CORE_TEMPERATURE = 14
    BOARD_TEMPERATURE = 15
    SET_VOLTAGE_LIMIT = 17
    SET_CURRENT_LIMIT = 18
    CC_CV_MODE = 20
    POWER_STATE = 21
    FAULT_STATE = 22
    STATE_MACHINE_FLAG_BITS = 23
    STATE_MACHINE_STATE = 24
    INPUT_VOLTAGE_RAW = 25
    INPUT_CURRENT_RAW = 26
    OUTPUT_VOLTAGE_RAW = 27
    OUTPUT_CURRENT_RAW = 28
    OTP_VALUE = 29
    OTP_SET_VALUE = 30
    OVP_VALUE = 31
    OVP_SET_VALUE = 32
    OCP_VALUE = 33
    OCP_SET_VALUE = 34
    FAN_SPEED = 38
    FAN_SET_VALUE = 39
    APP_TVL_DEBUG_SNAPSHOT = 40


class PowerValueType(IntEnum):
    U8 = 1
    U32 = 4


class PowerAccess(IntEnum):
    READ = 0x01
    WRITE = 0x02
    READ_WRITE = 0x03


@dataclass(frozen=True)
class PowerDataMeta:
    type_id: PowerDataType
    value_type: PowerValueType
    access: PowerAccess
    unit: str
    label: str

    @property
    def length(self) -> int:
        return int(self.value_type)


class FaultFlag(IntEnum):
    INPUT_UNDER_VOLTAGE = 0x0001
    INPUT_OVER_VOLTAGE = 0x0002
    OUTPUT_UNDER_VOLTAGE = 0x0004
    OUTPUT_OVER_VOLTAGE = 0x0008
    OUTPUT_OVER_CURRENT = 0x0010
    OUTPUT_SHORT_CIRCUIT = 0x0020
    OVER_TEMPERATURE_PROTECTION = 0x0040


FAULT_NAMES = {
    FaultFlag.INPUT_UNDER_VOLTAGE: "Input Under Voltage",
    FaultFlag.INPUT_OVER_VOLTAGE: "Input Over Voltage",
    FaultFlag.OUTPUT_UNDER_VOLTAGE: "Output Under Voltage",
    FaultFlag.OUTPUT_OVER_VOLTAGE: "Output Over Voltage",
    FaultFlag.OUTPUT_OVER_CURRENT: "Output Over Current",
    FaultFlag.OUTPUT_SHORT_CIRCUIT: "Output Short Circuit",
    FaultFlag.OVER_TEMPERATURE_PROTECTION: "Over Temperature Protection",
}

STATE_FLAG_NAMES = {
    0b0001: "INIT",
    0b0010: "WAIT",
    0b0100: "RISE",
    0b1000: "RUN",
    0b1111: "ERR",
}

STATE_MACHINE_NAMES = {
    0: "NA",
    1: "BUCK",
    2: "BOOST",
    3: "MIX",
}

CC_CV_NAMES = {
    0: "CC",
    1: "CV",
}

SOF = b"\xAA\x55"

POWER_DATA_META: dict[PowerDataType, PowerDataMeta] = {
    PowerDataType.INPUT_VOLTAGE: PowerDataMeta(PowerDataType.INPUT_VOLTAGE, PowerValueType.U32, PowerAccess.READ, "mV", "Input Voltage"),
    PowerDataType.INPUT_CURRENT: PowerDataMeta(PowerDataType.INPUT_CURRENT, PowerValueType.U32, PowerAccess.READ, "mA", "Input Current"),
    PowerDataType.OUTPUT_VOLTAGE: PowerDataMeta(PowerDataType.OUTPUT_VOLTAGE, PowerValueType.U32, PowerAccess.READ, "mV", "Output Voltage"),
    PowerDataType.OUTPUT_CURRENT: PowerDataMeta(PowerDataType.OUTPUT_CURRENT, PowerValueType.U32, PowerAccess.READ, "mA", "Output Current"),
    PowerDataType.CORE_TEMPERATURE: PowerDataMeta(PowerDataType.CORE_TEMPERATURE, PowerValueType.U32, PowerAccess.READ, "mC", "Core Temperature"),
    PowerDataType.BOARD_TEMPERATURE: PowerDataMeta(PowerDataType.BOARD_TEMPERATURE, PowerValueType.U32, PowerAccess.READ, "mC", "Board Temperature"),
    PowerDataType.SET_VOLTAGE_LIMIT: PowerDataMeta(PowerDataType.SET_VOLTAGE_LIMIT, PowerValueType.U32, PowerAccess.READ_WRITE, "mV", "Set Voltage Limit"),
    PowerDataType.SET_CURRENT_LIMIT: PowerDataMeta(PowerDataType.SET_CURRENT_LIMIT, PowerValueType.U32, PowerAccess.READ_WRITE, "mA", "Set Current Limit"),
    PowerDataType.CC_CV_MODE: PowerDataMeta(PowerDataType.CC_CV_MODE, PowerValueType.U8, PowerAccess.READ, "enum", "CC/CV Mode"),
    PowerDataType.POWER_STATE: PowerDataMeta(PowerDataType.POWER_STATE, PowerValueType.U8, PowerAccess.READ_WRITE, "bool", "Power State"),
    PowerDataType.FAULT_STATE: PowerDataMeta(PowerDataType.FAULT_STATE, PowerValueType.U32, PowerAccess.READ, "bitmask", "Fault State"),
    PowerDataType.STATE_MACHINE_FLAG_BITS: PowerDataMeta(PowerDataType.STATE_MACHINE_FLAG_BITS, PowerValueType.U8, PowerAccess.READ, "enum", "State Machine Flag Bits"),
    PowerDataType.STATE_MACHINE_STATE: PowerDataMeta(PowerDataType.STATE_MACHINE_STATE, PowerValueType.U8, PowerAccess.READ, "enum", "State Machine State"),
    PowerDataType.INPUT_VOLTAGE_RAW: PowerDataMeta(PowerDataType.INPUT_VOLTAGE_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Input Voltage Raw"),
    PowerDataType.INPUT_CURRENT_RAW: PowerDataMeta(PowerDataType.INPUT_CURRENT_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Input Current Raw"),
    PowerDataType.OUTPUT_VOLTAGE_RAW: PowerDataMeta(PowerDataType.OUTPUT_VOLTAGE_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Output Voltage Raw"),
    PowerDataType.OUTPUT_CURRENT_RAW: PowerDataMeta(PowerDataType.OUTPUT_CURRENT_RAW, PowerValueType.U32, PowerAccess.READ, "adc", "Output Current Raw"),
    PowerDataType.OTP_VALUE: PowerDataMeta(PowerDataType.OTP_VALUE, PowerValueType.U32, PowerAccess.READ, "mC", "OTP Value"),
    PowerDataType.OTP_SET_VALUE: PowerDataMeta(PowerDataType.OTP_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "mC", "OTP Set Value"),
    PowerDataType.OVP_VALUE: PowerDataMeta(PowerDataType.OVP_VALUE, PowerValueType.U32, PowerAccess.READ, "mV", "OVP Value"),
    PowerDataType.OVP_SET_VALUE: PowerDataMeta(PowerDataType.OVP_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "mV", "OVP Set Value"),
    PowerDataType.OCP_VALUE: PowerDataMeta(PowerDataType.OCP_VALUE, PowerValueType.U32, PowerAccess.READ, "mA", "OCP Value"),
    PowerDataType.OCP_SET_VALUE: PowerDataMeta(PowerDataType.OCP_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "mA", "OCP Set Value"),
    PowerDataType.FAN_SPEED: PowerDataMeta(PowerDataType.FAN_SPEED, PowerValueType.U32, PowerAccess.READ, "permille", "Fan Speed"),
    PowerDataType.FAN_SET_VALUE: PowerDataMeta(PowerDataType.FAN_SET_VALUE, PowerValueType.U32, PowerAccess.READ_WRITE, "permille", "Fan Set Value"),
}

TYPE_LENGTHS = {type_id: meta.length for type_id, meta in POWER_DATA_META.items()}

POWER_STATUS_FIELD_MAP = {
    PowerDataType.INPUT_VOLTAGE: "vin_mv",
    PowerDataType.INPUT_CURRENT: "iin_ma",
    PowerDataType.OUTPUT_VOLTAGE: "vout_mv",
    PowerDataType.OUTPUT_CURRENT: "iout_ma",
    PowerDataType.CORE_TEMPERATURE: "core_temp_mc",
    PowerDataType.BOARD_TEMPERATURE: "board_temp_mc",
    PowerDataType.SET_VOLTAGE_LIMIT: "set_voltage_limit_mv",
    PowerDataType.SET_CURRENT_LIMIT: "set_current_limit_ma",
    PowerDataType.CC_CV_MODE: "cc_cv_mode",
    PowerDataType.POWER_STATE: "power_state",
    PowerDataType.FAULT_STATE: "fault_state",
    PowerDataType.STATE_MACHINE_FLAG_BITS: "state_machine_flag_bits",
    PowerDataType.STATE_MACHINE_STATE: "state_machine_state",
    PowerDataType.OTP_VALUE: "otp_value_mc",
    PowerDataType.OTP_SET_VALUE: "otp_set_value_mc",
    PowerDataType.OVP_VALUE: "ovp_value_mv",
    PowerDataType.OVP_SET_VALUE: "ovp_set_value_mv",
    PowerDataType.OCP_VALUE: "ocp_value_ma",
    PowerDataType.OCP_SET_VALUE: "ocp_set_value_ma",
    PowerDataType.FAN_SPEED: "fan_speed",
    PowerDataType.FAN_SET_VALUE: "fan_set_value",
}

STATUS_TYPES = (
    PowerDataType.INPUT_VOLTAGE,
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_VOLTAGE,
    PowerDataType.OUTPUT_CURRENT,
    PowerDataType.CORE_TEMPERATURE,
    PowerDataType.BOARD_TEMPERATURE,
    PowerDataType.SET_VOLTAGE_LIMIT,
    PowerDataType.SET_CURRENT_LIMIT,
    PowerDataType.CC_CV_MODE,
    PowerDataType.POWER_STATE,
    PowerDataType.FAULT_STATE,
    PowerDataType.STATE_MACHINE_FLAG_BITS,
    PowerDataType.STATE_MACHINE_STATE,
    PowerDataType.OTP_VALUE,
    PowerDataType.OTP_SET_VALUE,
    PowerDataType.OVP_VALUE,
    PowerDataType.OVP_SET_VALUE,
    PowerDataType.OCP_VALUE,
    PowerDataType.OCP_SET_VALUE,
    PowerDataType.FAN_SPEED,
    PowerDataType.FAN_SET_VALUE,
)

REPORT_STATUS_TYPES = (
    PowerDataType.INPUT_VOLTAGE,
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_VOLTAGE,
    PowerDataType.OUTPUT_CURRENT,
    PowerDataType.CORE_TEMPERATURE,
    PowerDataType.BOARD_TEMPERATURE,
    PowerDataType.SET_VOLTAGE_LIMIT,
    PowerDataType.SET_CURRENT_LIMIT,
    PowerDataType.CC_CV_MODE,
    PowerDataType.POWER_STATE,
    PowerDataType.FAULT_STATE,
    PowerDataType.STATE_MACHINE_FLAG_BITS,
    PowerDataType.STATE_MACHINE_STATE,
    PowerDataType.OTP_SET_VALUE,
    PowerDataType.OVP_SET_VALUE,
    PowerDataType.OCP_SET_VALUE,
    PowerDataType.FAN_SPEED,
)


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _u32(value: int) -> bytes:
    return int(value).to_bytes(4, "little", signed=False)


def _u8(value: int) -> bytes:
    return int(value).to_bytes(1, "little", signed=False)


def encode_tlv(type_id: PowerDataType | int, value: bytes = b"") -> bytes:
    raw_type = int(type_id) & 0xFF
    raw_value = bytes(value)
    return bytes([raw_type]) + len(raw_value).to_bytes(2, "little") + raw_value


def decode_tlvs(payload: bytes, *, strict: bool = True) -> dict[PowerDataType, int]:
    offset = 0
    items: dict[PowerDataType, int] = {}

    while offset < len(payload):
        if offset + 3 > len(payload):
            raise PowerClientProtocolError("Incomplete TLV header")

        type_id = payload[offset]
        offset += 1
        length = int.from_bytes(payload[offset:offset + 2], "little")
        offset += 2

        if offset + length > len(payload):
            raise PowerClientProtocolError(f"Incomplete TLV value for type {type_id}")

        value = payload[offset:offset + length]
        offset += length

        try:
            data_type = PowerDataType(type_id)
        except ValueError as exc:
            if not strict:
                continue
            raise PowerClientProtocolError(f"Unknown data type {type_id}") from exc

        expected_length = TYPE_LENGTHS.get(data_type)
        if expected_length is not None and length != expected_length:
            if not strict:
                continue
            raise PowerClientProtocolError(
                f"Unexpected length {length} for {data_type.name}, expected {expected_length}"
            )

        items[data_type] = int.from_bytes(value, "little", signed=False)

    return items


def _ensure_readable(type_id: PowerDataType) -> None:
    meta = POWER_DATA_META.get(type_id)
    if meta is not None and not (int(meta.access) & int(PowerAccess.READ)):
        raise PowerClientAccessError(f"{type_id.name} is not readable")


def _ensure_writable(type_id: PowerDataType, value: bytes) -> None:
    meta = POWER_DATA_META.get(type_id)
    if meta is None:
        raise PowerClientAccessError(f"{type_id.name} has no writable metadata")
    if not (int(meta.access) & int(PowerAccess.WRITE)):
        raise PowerClientAccessError(f"{type_id.name} is not writable")
    if len(value) != meta.length:
        raise PowerClientProtocolError(
            f"Unexpected write length {len(value)} for {type_id.name}, expected {meta.length}"
        )


def build_frame(cmd: PowerCommand | int, seq: int, payload: bytes) -> bytes:
    body = bytes([int(cmd) & 0xFF, seq & 0xFF]) + payload
    frame = bytearray(SOF)
    frame.extend(len(body).to_bytes(2, "little"))
    frame.extend(body)
    frame.extend(crc16_modbus(frame).to_bytes(2, "little"))
    return bytes(frame)


def build_status(values: dict[PowerDataType, int]) -> PowerStatus:
    normalized = _normalize_status_values(values)
    missing = [type_id.name for type_id in STATUS_TYPES if type_id not in normalized]
    if missing:
        raise PowerClientProtocolError(f"Missing status types: {', '.join(missing)}")
    return PowerStatus(
        vin_mv=normalized[PowerDataType.INPUT_VOLTAGE],
        iin_ma=normalized[PowerDataType.INPUT_CURRENT],
        vout_mv=normalized[PowerDataType.OUTPUT_VOLTAGE],
        iout_ma=normalized[PowerDataType.OUTPUT_CURRENT],
        core_temp_mc=normalized[PowerDataType.CORE_TEMPERATURE],
        board_temp_mc=normalized[PowerDataType.BOARD_TEMPERATURE],
        set_voltage_limit_mv=normalized[PowerDataType.SET_VOLTAGE_LIMIT],
        set_current_limit_ma=normalized[PowerDataType.SET_CURRENT_LIMIT],
        cc_cv_mode=normalized[PowerDataType.CC_CV_MODE],
        power_state=normalized[PowerDataType.POWER_STATE],
        fault_state=normalized[PowerDataType.FAULT_STATE],
        state_machine_flag_bits=normalized[PowerDataType.STATE_MACHINE_FLAG_BITS],
        state_machine_state=normalized[PowerDataType.STATE_MACHINE_STATE],
        otp_value_mc=normalized[PowerDataType.OTP_VALUE],
        otp_set_value_mc=normalized[PowerDataType.OTP_SET_VALUE],
        ovp_value_mv=normalized[PowerDataType.OVP_VALUE],
        ovp_set_value_mv=normalized[PowerDataType.OVP_SET_VALUE],
        ocp_value_ma=normalized[PowerDataType.OCP_VALUE],
        ocp_set_value_ma=normalized[PowerDataType.OCP_SET_VALUE],
        fan_speed=normalized[PowerDataType.FAN_SPEED],
        fan_set_value=normalized[PowerDataType.FAN_SET_VALUE],
    )


def _normalize_status_values(values: dict[PowerDataType, int]) -> dict[PowerDataType, int]:
    normalized = dict(values)
    if PowerDataType.OTP_VALUE not in normalized and PowerDataType.BOARD_TEMPERATURE in normalized:
        normalized[PowerDataType.OTP_VALUE] = normalized[PowerDataType.BOARD_TEMPERATURE]
    if PowerDataType.OVP_VALUE not in normalized and PowerDataType.OUTPUT_VOLTAGE in normalized:
        normalized[PowerDataType.OVP_VALUE] = normalized[PowerDataType.OUTPUT_VOLTAGE]
    if PowerDataType.OCP_VALUE not in normalized and PowerDataType.OUTPUT_CURRENT in normalized:
        normalized[PowerDataType.OCP_VALUE] = normalized[PowerDataType.OUTPUT_CURRENT]
    if PowerDataType.FAN_SET_VALUE not in normalized and PowerDataType.FAN_SPEED in normalized:
        normalized[PowerDataType.FAN_SET_VALUE] = normalized[PowerDataType.FAN_SPEED]
    return normalized


@dataclass(frozen=True)
class PowerStatus:
    vin_mv: int
    iin_ma: int
    vout_mv: int
    iout_ma: int
    core_temp_mc: int
    board_temp_mc: int
    set_voltage_limit_mv: int
    set_current_limit_ma: int
    cc_cv_mode: int
    power_state: int
    fault_state: int
    state_machine_flag_bits: int
    state_machine_state: int
    otp_value_mc: int
    otp_set_value_mc: int
    ovp_value_mv: int
    ovp_set_value_mv: int
    ocp_value_ma: int
    ocp_set_value_ma: int
    fan_speed: int
    fan_set_value: int

    @property
    def vin_v(self) -> float:
        return self.vin_mv / 1000.0

    @property
    def iin_a(self) -> float:
        return self.iin_ma / 1000.0

    @property
    def vout_v(self) -> float:
        return self.vout_mv / 1000.0

    @property
    def iout_a(self) -> float:
        return self.iout_ma / 1000.0

    @property
    def pout_w(self) -> float:
        return self.vout_v * self.iout_a

    @property
    def pin_w(self) -> float:
        return self.vin_v * self.iin_a

    @property
    def efficiency(self) -> float:
        return 0.0 if self.pin_w <= 0 else (self.pout_w / self.pin_w) * 100.0

    @property
    def core_temp_c(self) -> float:
        return self.core_temp_mc / 1000.0

    @property
    def board_temp_c(self) -> float:
        return self.board_temp_mc / 1000.0

    @property
    def otp_value_c(self) -> float:
        return self.otp_value_mc / 1000.0

    @property
    def otp_set_value_c(self) -> float:
        return self.otp_set_value_mc / 1000.0

    @property
    def ovp_value_v(self) -> float:
        return self.ovp_value_mv / 1000.0

    @property
    def ovp_set_value_v(self) -> float:
        return self.ovp_set_value_mv / 1000.0

    @property
    def ocp_value_a(self) -> float:
        return self.ocp_value_ma / 1000.0

    @property
    def ocp_set_value_a(self) -> float:
        return self.ocp_set_value_ma / 1000.0

    @property
    def mode_name(self) -> str:
        return CC_CV_NAMES.get(self.cc_cv_mode, f"UNKNOWN({self.cc_cv_mode})")

    @property
    def topology_name(self) -> str:
        return STATE_MACHINE_NAMES.get(self.state_machine_state, f"UNKNOWN({self.state_machine_state})")

    @property
    def state_flag_name(self) -> str:
        return STATE_FLAG_NAMES.get(self.state_machine_flag_bits, f"0b{self.state_machine_flag_bits:04b}")

    @property
    def power_enabled(self) -> bool:
        return bool(self.power_state)


@dataclass(frozen=True)
class DebugSnapshot:
    output_voltage_raw: int
    output_voltage_mv: int
    ovp_set_value_mv: int

    @property
    def output_voltage_v(self) -> float:
        return self.output_voltage_mv / 1000.0

    @property
    def ovp_set_value_v(self) -> float:
        return self.ovp_set_value_mv / 1000.0


@dataclass
class _PendingRequest:
    seq: int
    loop: QEventLoop
    response: dict[PowerDataType, int] | None = None
    error: Exception | None = None


class F4CPPowerClient(QObject):
    log = pyqtSignal(str)
    error = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    statusUpdated = pyqtSignal(object)
    debugSnapshotReady = pyqtSignal(object)
    outputLimitsWritten = pyqtSignal()
    protectionValuesWritten = pyqtSignal()
    powerStateWritten = pyqtSignal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._session: SerialSession | None = None
        self._buffer = bytearray()
        self._seq = 0
        self._pending: _PendingRequest | None = None
        self._last_values: dict[PowerDataType, int] = {}
        self._last_status: PowerStatus | None = None
        self._shutting_down = False
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_once)

    @property
    def is_connected(self) -> bool:
        return self._session is not None and self._session.is_open

    @property
    def is_busy(self) -> bool:
        return self._pending is not None

    @pyqtSlot(object)
    def attach_session(self, session: SerialSession) -> None:
        self._shutting_down = False
        self._session = session
        self._buffer.clear()
        self._pending = None
        self._last_values.clear()
        self._last_status = None
        session.set_event_receiver(self)
        self.connectionChanged.emit(session.is_open)
        self.log.emit(f"Attached to serial session on {session.cfg.port}")

    @pyqtSlot()
    def detach_session(self) -> None:
        self.stop_polling()
        self._fail_pending(PowerClientError("Serial session detached"))
        if self._session is not None:
            try:
                self._session.set_event_receiver(None)
            except Exception:
                pass
        self._session = None
        self._buffer.clear()
        self._pending = None
        self._last_values.clear()
        self._last_status = None
        self.connectionChanged.emit(False)

    @pyqtSlot()
    def shutdown(self) -> None:
        self._shutting_down = True
        self.stop_polling()
        self.detach_session()

    @pyqtSlot(int)
    def start_polling(self, interval_ms: int = 800) -> None:
        interval = max(200, int(interval_ms))
        was_active = self._poll_timer.isActive()
        previous_interval = self._poll_timer.interval()
        self._poll_timer.start(interval)
        if (not was_active) or previous_interval != interval:
            self.log.emit(f"Host polling started ({interval} ms)")
        if self.is_connected and not self.is_busy:
            QTimer.singleShot(0, self._poll_once)

    @pyqtSlot()
    def stop_polling(self) -> None:
        self._poll_timer.stop()

    @pyqtSlot()
    def request_read_status(self) -> None:
        if not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=1000)
        except Exception as exc:
            self.error.emit(str(exc))

    @pyqtSlot()
    def request_debug_snapshot(self) -> None:
        if not self.is_connected or self.is_busy:
            return
        try:
            snapshot = self.read_debug_snapshot(timeout_ms=1000)
            self.debugSnapshotReady.emit(snapshot)
        except Exception as exc:
            self.error.emit(str(exc))

    @pyqtSlot(int, int, bool)
    def request_set_output_limits(self, voltage_mv: int, current_ma: int, enabled: bool) -> None:
        if not self.is_connected:
            self.error.emit("Serial session is not connected")
            return
        if self.is_busy:
            self.error.emit("Another request is still pending; output write was not sent")
            return
        try:
            self.write_values(
                {
                    PowerDataType.SET_VOLTAGE_LIMIT: _u32(voltage_mv),
                    PowerDataType.SET_CURRENT_LIMIT: _u32(current_ma),
                    PowerDataType.POWER_STATE: _u8(1 if enabled else 0),
                },
                timeout_ms=1000,
            )
            self.outputLimitsWritten.emit()
            self._refresh_status_after_write(timeout_ms=1000)
        except Exception as exc:
            self.error.emit(str(exc))

    @pyqtSlot(int, int, int, int)
    def request_set_protection_values(self, ovp_mv: int, ocp_ma: int, otp_mc: int, fan_value: int) -> None:
        if not self.is_connected:
            self.error.emit("Serial session is not connected")
            return
        if self.is_busy:
            self.error.emit("Another request is still pending; protection write was not sent")
            return
        try:
            self.write_values(
                {
                    PowerDataType.OVP_SET_VALUE: _u32(ovp_mv),
                    PowerDataType.OCP_SET_VALUE: _u32(ocp_ma),
                    PowerDataType.OTP_SET_VALUE: _u32(otp_mc),
                    PowerDataType.FAN_SET_VALUE: _u32(fan_value),
                },
                timeout_ms=1000,
            )
            self.protectionValuesWritten.emit()
            self._refresh_status_after_write(timeout_ms=1000)
        except Exception as exc:
            self.error.emit(str(exc))

    @pyqtSlot(bool)
    def request_set_power_state(self, enabled: bool) -> None:
        if not self.is_connected:
            self.error.emit("Serial session is not connected")
            return
        if self.is_busy:
            self.error.emit("Another request is still pending; power state write was not sent")
            return
        try:
            self.set_power_state(enabled, timeout_ms=1000)
            self.powerStateWritten.emit(enabled)
            self._refresh_status_after_write(timeout_ms=1000)
        except Exception as exc:
            self.error.emit(str(exc))

    def event(self, event):
        event_type = event.type()

        if event_type == int(SerialEventType.RX):
            self._handle_rx(event)
            return True

        if event_type == int(SerialEventType.TX):
            self._handle_tx(event)
            return True

        if event_type == int(SerialEventType.ERROR):
            self._handle_error(event)
            return True

        if event_type == int(SerialEventType.STATE):
            self._handle_state(event)
            return True

        return super().event(event)

    def read_values(self, *types: PowerDataType, timeout_ms: int = 1000) -> dict[PowerDataType, int]:
        for type_id in types:
            _ensure_readable(type_id)
        payload = b"".join(encode_tlv(type_id) for type_id in types)
        response = self._request(PowerCommand.READ, payload, timeout_ms=timeout_ms)

        if types == (PowerDataType.APP_TVL_DEBUG_SNAPSHOT,):
            return response

        missing = [type_id.name for type_id in types if type_id not in response]
        if missing:
            raise PowerClientProtocolError(f"Missing response types: {', '.join(missing)}")
        self._last_values.update(response)
        return response

    def write_values(self, values: dict[PowerDataType, bytes], timeout_ms: int = 1000) -> None:
        for type_id, raw_value in values.items():
            _ensure_writable(type_id, raw_value)
        payload = b"".join(encode_tlv(type_id, raw_value) for type_id, raw_value in values.items())
        self._request(PowerCommand.WRITE, payload, timeout_ms=timeout_ms)
        self._last_values.update(
            {
                type_id: int.from_bytes(raw_value, "little", signed=False)
                for type_id, raw_value in values.items()
            }
        )

    def read_status(self, timeout_ms: int = 1000) -> PowerStatus:
        result = self.read_values(*STATUS_TYPES, timeout_ms=timeout_ms)
        status = build_status(result)
        self._last_status = status
        self.statusUpdated.emit(status)
        return status

    def read_debug_snapshot(self, timeout_ms: int = 1000) -> DebugSnapshot:
        result = self.read_values(PowerDataType.APP_TVL_DEBUG_SNAPSHOT, timeout_ms=timeout_ms)

        missing = [
            type_id.name
            for type_id in (
                PowerDataType.OUTPUT_VOLTAGE_RAW,
                PowerDataType.OUTPUT_VOLTAGE,
                PowerDataType.OVP_SET_VALUE,
            )
            if type_id not in result
        ]
        if missing:
            raise PowerClientProtocolError(f"Debug snapshot missing response types: {', '.join(missing)}")

        return DebugSnapshot(
            output_voltage_raw=result[PowerDataType.OUTPUT_VOLTAGE_RAW],
            output_voltage_mv=result[PowerDataType.OUTPUT_VOLTAGE],
            ovp_set_value_mv=result[PowerDataType.OVP_SET_VALUE],
        )

    def set_voltage_limit_mv(self, value_mv: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.SET_VOLTAGE_LIMIT: _u32(value_mv)}, timeout_ms=timeout_ms)

    def set_current_limit_ma(self, value_ma: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.SET_CURRENT_LIMIT: _u32(value_ma)}, timeout_ms=timeout_ms)

    def set_ovp_mv(self, value_mv: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.OVP_SET_VALUE: _u32(value_mv)}, timeout_ms=timeout_ms)

    def set_ocp_ma(self, value_ma: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.OCP_SET_VALUE: _u32(value_ma)}, timeout_ms=timeout_ms)

    def set_otp_mc(self, value_mc: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.OTP_SET_VALUE: _u32(value_mc)}, timeout_ms=timeout_ms)

    def set_fan_value(self, value: int, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.FAN_SET_VALUE: _u32(value)}, timeout_ms=timeout_ms)

    def set_power_state(self, enabled: bool, timeout_ms: int = 1000) -> None:
        self.write_values({PowerDataType.POWER_STATE: _u8(1 if enabled else 0)}, timeout_ms=timeout_ms)

    def set_output(
        self,
        voltage_v: float,
        current_a: float,
        enabled: bool = True,
        timeout_ms: int = 1000,
    ) -> None:
        self.write_values(
            {
                PowerDataType.SET_VOLTAGE_LIMIT: _u32(int(voltage_v * 1000 + 0.5)),
                PowerDataType.SET_CURRENT_LIMIT: _u32(int(current_a * 1000 + 0.5)),
                PowerDataType.POWER_STATE: _u8(1 if enabled else 0),
            },
            timeout_ms=timeout_ms,
        )

    def pretty_print_status(self, status: PowerStatus) -> str:
        faults = ", ".join(self.decode_fault_flags(status.fault_state)) or "None"
        return (
            f"VIN={status.vin_v:.3f} V, IIN={status.iin_a:.3f} A, "
            f"VOUT={status.vout_v:.3f} V, IOUT={status.iout_a:.3f} A, "
            f"Mode={status.mode_name}, Topology={status.topology_name}, "
            f"Power={'ON' if status.power_enabled else 'OFF'}, Faults={faults}"
        )

    @staticmethod
    def pretty_print_debug_snapshot(snapshot: DebugSnapshot) -> str:
        return (
            "DEBUG_SNAPSHOT "
            f"raw27={snapshot.output_voltage_raw}, "
            f"vout12={snapshot.output_voltage_mv} mV ({snapshot.output_voltage_v:.3f} V), "
            f"ovp32={snapshot.ovp_set_value_mv} mV ({snapshot.ovp_set_value_v:.3f} V)"
        )

    @staticmethod
    def decode_fault_flags(mask: int) -> list[str]:
        if mask == 0:
            return []
        return [name for flag, name in FAULT_NAMES.items() if mask & int(flag)]

    @staticmethod
    def decode_state_flag(value: int) -> str:
        return STATE_FLAG_NAMES.get(value, f"0b{value:04b}")

    @staticmethod
    def decode_topology(value: int) -> str:
        return STATE_MACHINE_NAMES.get(value, f"UNKNOWN({value})")

    @staticmethod
    def decode_cc_cv(value: int) -> str:
        return CC_CV_NAMES.get(value, f"UNKNOWN({value})")

    def _poll_once(self) -> None:
        if self._shutting_down or not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=800)
        except Exception as exc:
            self.error.emit(str(exc))

    def _refresh_status_after_write(self, timeout_ms: int = 1000) -> None:
        if self._shutting_down or not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=timeout_ms)
        except Exception as exc:
            self.error.emit(f"WRITE ACK received, but status refresh failed: {exc}")

    def _request(self, cmd: PowerCommand, payload: bytes, timeout_ms: int = 1000) -> dict[PowerDataType, int]:
        if not self.is_connected or self._session is None:
            raise PowerClientError("Serial session is not connected")
        if self._pending is not None:
            raise PowerClientError("Another request is still pending")

        self._seq = (self._seq + 1) & 0xFF
        seq = self._seq
        frame = build_frame(cmd, seq, payload)
        loop = QEventLoop(self)
        pending = _PendingRequest(seq=seq, loop=loop)
        self._pending = pending

        timer = QTimer(self)
        timer.setSingleShot(True)

        def _on_timeout():
            if self._pending is pending and pending.error is None and pending.response is None:
                pending.error = PowerClientTimeoutError(f"Request timed out for seq={seq}")
                pending.loop.quit()

        timer.timeout.connect(_on_timeout)
        timer.start(timeout_ms)

        QCoreApplication.postEvent(self._session, SendEvent(frame))
        self.log.emit(f"REQ cmd=0x{int(cmd):02X} seq={seq} len={len(payload)}")
        pending.loop.exec_()

        timer.stop()
        timer.deleteLater()
        self._pending = None

        if pending.error is not None:
            raise pending.error
        return pending.response or {}

    def _handle_rx(self, event: RxEvent) -> None:
        data = event.payload.data
        if not data:
            return
        self.log.emit(f"RX {data.hex(' ')}")
        self._buffer.extend(data)

        while True:
            try:
                frame = self._extract_frame()
            except Exception as exc:
                self._fail_pending(exc)
                self.error.emit(str(exc))
                return

            if frame is None:
                break

            if int(frame["cmd"]) == int(PowerCommand.REPORT):
                self._handle_report(frame)
                continue

            try:
                response = self._parse_response(frame)
            except Exception as exc:
                self._fail_pending(exc)
                self.error.emit(str(exc))
                continue

            if self._pending is None:
                self.log.emit("Ignored unsolicited response frame")
                continue

            if frame["seq"] != self._pending.seq:
                self._fail_pending(
                    PowerClientProtocolError(
                        f"Response seq mismatch: expected {self._pending.seq}, got {frame['seq']}"
                    )
                )
                continue

            self._pending.response = response
            self._pending.loop.quit()

    def _handle_report(self, frame: dict[str, int | bytes]) -> None:
        if int(frame["seq"]) != 0:
            self.error.emit(f"REPORT seq should be 0, got {frame['seq']}")
            return

        try:
            values = decode_tlvs(bytes(frame["payload"]), strict=False)
        except Exception as exc:
            self.error.emit(str(exc))
            return

        self._last_values.update(values)
        self.log.emit(
            f"REPORT seq=0 types={','.join(type_id.name for type_id in values)}"
        )
        status = self._status_from_values(values)
        if status is None:
            missing = [type_id.name for type_id in STATUS_TYPES if type_id not in _normalize_status_values(self._last_values)]
            self.log.emit(f"REPORT cached, waiting for fields: {','.join(missing)}")
            return
        self._last_status = status
        self.statusUpdated.emit(status)

    def _status_from_values(self, values: dict[PowerDataType, int]) -> PowerStatus | None:
        values = _normalize_status_values(values)
        if self._last_status is None:
            try:
                return build_status(self._last_values)
            except PowerClientProtocolError:
                return None

        updates = {}
        for type_id, value in values.items():
            field_name = POWER_STATUS_FIELD_MAP.get(type_id)
            if field_name is not None:
                updates[field_name] = value

        return replace(self._last_status, **updates) if updates else self._last_status

    def _handle_tx(self, event: TxEvent) -> None:
        self.log.emit(f"TX {event.payload.data.hex(' ')}")

    def _handle_error(self, event: ErrorEvent) -> None:
        message = event.payload.message
        self._fail_pending(PowerClientError(message))
        self.error.emit(message)

    def _handle_state(self, event: StateEvent) -> None:
        state = event.payload.state
        is_open = state == SerialState.OPEN
        self.connectionChanged.emit(is_open)
        if state == SerialState.CLOSED:
            self.stop_polling()
            self._fail_pending(PowerClientError("Serial port closed"))
        elif state == SerialState.ERROR:
            self._fail_pending(PowerClientError(event.payload.info or "Serial port error"))

    def _extract_frame(self) -> dict[str, int | bytes] | None:
        while len(self._buffer) >= 2 and self._buffer[:2] != SOF:
            self._buffer.pop(0)

        if len(self._buffer) < 6:
            return None

        body_len = int.from_bytes(self._buffer[2:4], "little")
        total_len = 2 + 2 + body_len + 2
        if len(self._buffer) < total_len:
            return None

        raw = bytes(self._buffer[:total_len])
        del self._buffer[:total_len]

        expected_crc = int.from_bytes(raw[-2:], "little")
        actual_crc = crc16_modbus(raw[:-2])
        if expected_crc != actual_crc:
            raise PowerClientCrcError(
                f"CRC mismatch: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}"
            )

        if body_len < 2:
            raise PowerClientProtocolError("Body length is too short")

        return {
            "cmd": raw[4],
            "seq": raw[5],
            "payload": raw[6:-2],
        }

    def _parse_response(self, frame: dict[str, int | bytes]) -> dict[PowerDataType, int]:
        cmd = int(frame["cmd"])
        payload = bytes(frame["payload"])

        if cmd == int(PowerCommand.NACK):
            raise PowerClientNackError(f"Device returned NACK for seq={frame['seq']}")
        if cmd != int(PowerCommand.ACK):
            raise PowerClientProtocolError(f"Unexpected response cmd=0x{cmd:02X}")
        return decode_tlvs(payload)

    def _fail_pending(self, exc: Exception) -> None:
        if self._pending is None:
            return
        self._pending.error = exc
        self._pending.loop.quit()


def pretty_faults(mask: int) -> str:
    return ", ".join(F4CPPowerClient.decode_fault_flags(mask)) or "None"


def pack_read_request(types: Iterable[PowerDataType]) -> bytes:
    return b"".join(encode_tlv(item) for item in types)


class TVLHost:
    """Reusable QSerialPort host for the F4CP power protocol."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        self._serial = QSerialPort()
        self._serial.setPortName(port)
        self._serial.setBaudRate(baudrate)
        self._serial.setDataBits(QSerialPort.DataBits.Data8)
        self._serial.setParity(QSerialPort.Parity.NoParity)
        self._serial.setStopBits(QSerialPort.StopBits.OneStop)
        if not self._serial.open(QIODevice.OpenModeFlag.ReadWrite):
            raise PowerClientError(
                f"Serial port open failed {port}: {self._serial.errorString()}"
            )
        self._timeout = float(timeout)
        self._seq = 0
        self._buffer = bytearray()
        self._last_values: dict[PowerDataType, int] = {}

    def close(self) -> None:
        if self._serial.isOpen():
            self._serial.close()

    def send_frame(self, cmd: PowerCommand | int, seq: int, payload: bytes) -> None:
        data = build_frame(cmd, seq, payload)
        written = self._serial.write(data)
        if written != len(data):
            raise PowerClientError(
                f"Serial write incomplete: expected {len(data)}, wrote {written}"
            )
        if not self._serial.waitForBytesWritten(max(1, int(self._timeout * 1000))):
            raise PowerClientTimeoutError("Serial write timed out")

    def recv_frame(self, timeout: float | None = None) -> dict[str, int | bytes]:
        deadline = time.monotonic() + (self._timeout if timeout is None else timeout)
        while time.monotonic() < deadline:
            frame = self._extract_buffered_frame()
            if frame is not None:
                return frame

            wait_ms = max(1, min(50, int((deadline - time.monotonic()) * 1000)))
            if not self._serial.waitForReadyRead(wait_ms):
                continue

            raw = self._serial.readAll()
            chunk = raw.data() if hasattr(raw, "data") else bytes(raw)
            if chunk:
                self._buffer.extend(chunk)

        raise PowerClientTimeoutError("Receive timed out")

    def read_values(
        self,
        *types: PowerDataType,
        timeout: float | None = None,
    ) -> dict[PowerDataType, int]:
        for type_id in types:
            _ensure_readable(type_id)
        payload = b"".join(encode_tlv(type_id) for type_id in types)
        values = self._request(PowerCommand.READ, payload, timeout=timeout)
        missing = [type_id.name for type_id in types if type_id not in values]
        if missing:
            raise PowerClientProtocolError(f"Missing response types: {', '.join(missing)}")
        self._last_values.update(values)
        return values

    def write_values(
        self,
        values: dict[PowerDataType, bytes],
        timeout: float | None = None,
    ) -> None:
        for type_id, raw_value in values.items():
            _ensure_writable(type_id, raw_value)
        payload = b"".join(encode_tlv(type_id, raw_value) for type_id, raw_value in values.items())
        self._request(PowerCommand.WRITE, payload, timeout=timeout)
        self._last_values.update(
            {
                type_id: int.from_bytes(raw_value, "little", signed=False)
                for type_id, raw_value in values.items()
            }
        )

    def read_status(self, timeout: float | None = None) -> PowerStatus:
        return build_status(self.read_values(*STATUS_TYPES, timeout=timeout))

    def set_voltage_limit_mv(self, value_mv: int) -> None:
        self.write_values({PowerDataType.SET_VOLTAGE_LIMIT: _u32(value_mv)})

    def set_current_limit_ma(self, value_ma: int) -> None:
        self.write_values({PowerDataType.SET_CURRENT_LIMIT: _u32(value_ma)})

    def set_ovp_mv(self, value_mv: int) -> None:
        self.write_values({PowerDataType.OVP_SET_VALUE: _u32(value_mv)})

    def set_ocp_ma(self, value_ma: int) -> None:
        self.write_values({PowerDataType.OCP_SET_VALUE: _u32(value_ma)})

    def set_otp_mc(self, value_mc: int) -> None:
        self.write_values({PowerDataType.OTP_SET_VALUE: _u32(value_mc)})

    def set_power_state(self, enabled: bool) -> None:
        self.write_values({PowerDataType.POWER_STATE: _u8(1 if enabled else 0)})

    def set_output(
        self,
        voltage_v: float,
        current_a: float,
        enabled: bool = True,
    ) -> None:
        self.write_values(
            {
                PowerDataType.SET_VOLTAGE_LIMIT: _u32(int(voltage_v * 1000 + 0.5)),
                PowerDataType.SET_CURRENT_LIMIT: _u32(int(current_a * 1000 + 0.5)),
                PowerDataType.POWER_STATE: _u8(1 if enabled else 0),
            }
        )

    def _request(
        self,
        cmd: PowerCommand,
        payload: bytes,
        timeout: float | None = None,
    ) -> dict[PowerDataType, int]:
        self._seq = (self._seq + 1) & 0xFF
        seq = self._seq
        self.send_frame(cmd, seq, payload)

        deadline = time.monotonic() + (self._timeout if timeout is None else timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PowerClientTimeoutError(f"Request timed out for seq={seq}")

            frame = self.recv_frame(timeout=remaining)
            frame_cmd = int(frame["cmd"])

            if frame_cmd == int(PowerCommand.REPORT):
                self._handle_report(frame)
                continue
            if frame_cmd == int(PowerCommand.NACK):
                raise PowerClientNackError(f"Device returned NACK for seq={frame['seq']}")
            if frame_cmd != int(PowerCommand.ACK):
                raise PowerClientProtocolError(f"Unexpected response cmd=0x{frame_cmd:02X}")
            if int(frame["seq"]) != seq:
                raise PowerClientProtocolError(
                    f"Response seq mismatch: expected {seq}, got {frame['seq']}"
                )
            return decode_tlvs(bytes(frame["payload"]))

    def _handle_report(self, frame: dict[str, int | bytes]) -> None:
        if int(frame["seq"]) != 0:
            raise PowerClientProtocolError(f"REPORT seq should be 0, got {frame['seq']}")
        self._last_values.update(decode_tlvs(bytes(frame["payload"]), strict=False))

    def _extract_buffered_frame(self) -> dict[str, int | bytes] | None:
        while len(self._buffer) >= 2 and self._buffer[:2] != SOF:
            self._buffer.pop(0)

        if len(self._buffer) < 6:
            return None

        body_len = int.from_bytes(self._buffer[2:4], "little")
        total_len = 2 + 2 + body_len + 2
        if len(self._buffer) < total_len:
            return None

        raw = bytes(self._buffer[:total_len])
        del self._buffer[:total_len]

        expected_crc = int.from_bytes(raw[-2:], "little")
        actual_crc = crc16_modbus(raw[:-2])
        if expected_crc != actual_crc:
            raise PowerClientCrcError(
                f"CRC mismatch: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}"
            )
        if body_len < 2:
            raise PowerClientProtocolError("Body length is too short")

        return {
            "cmd": raw[4],
            "seq": raw[5],
            "payload": raw[6:-2],
        }
