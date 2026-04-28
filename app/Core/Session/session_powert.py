# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

from PyQt5.QtCore import QCoreApplication, QEventLoop, QObject, QTimer, pyqtSignal

from app.Core.Session import (
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


class PowerCommand(IntEnum):
    ACK = 0x00
    READ = 0x01
    WRITE = 0x02
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

TYPE_LENGTHS = {
    PowerDataType.INPUT_VOLTAGE: 4,
    PowerDataType.INPUT_CURRENT: 4,
    PowerDataType.OUTPUT_VOLTAGE: 4,
    PowerDataType.OUTPUT_CURRENT: 4,
    PowerDataType.CORE_TEMPERATURE: 4,
    PowerDataType.BOARD_TEMPERATURE: 4,
    PowerDataType.SET_VOLTAGE_LIMIT: 4,
    PowerDataType.SET_CURRENT_LIMIT: 4,
    PowerDataType.CC_CV_MODE: 1,
    PowerDataType.POWER_STATE: 1,
    PowerDataType.FAULT_STATE: 4,
    PowerDataType.STATE_MACHINE_FLAG_BITS: 1,
    PowerDataType.STATE_MACHINE_STATE: 1,
    PowerDataType.INPUT_VOLTAGE_RAW: 4,
    PowerDataType.INPUT_CURRENT_RAW: 4,
    PowerDataType.OUTPUT_VOLTAGE_RAW: 4,
    PowerDataType.OUTPUT_CURRENT_RAW: 4,
    PowerDataType.OTP_VALUE: 4,
    PowerDataType.OTP_SET_VALUE: 4,
    PowerDataType.OVP_VALUE: 4,
    PowerDataType.OVP_SET_VALUE: 4,
    PowerDataType.OCP_VALUE: 4,
    PowerDataType.OCP_SET_VALUE: 4,
    PowerDataType.FAN_SPEED: 4,
    PowerDataType.FAN_SET_VALUE: 4,
}


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


def decode_tlvs(payload: bytes) -> dict[PowerDataType, int]:
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
            raise PowerClientProtocolError(f"Unknown data type {type_id}") from exc

        expected_length = TYPE_LENGTHS.get(data_type)
        if expected_length is not None and length != expected_length:
            raise PowerClientProtocolError(
                f"Unexpected length {length} for {data_type.name}, expected {expected_length}"
            )

        items[data_type] = int.from_bytes(value, "little", signed=False)

    return items


def build_frame(cmd: PowerCommand | int, seq: int, payload: bytes) -> bytes:
    body = bytes([int(cmd) & 0xFF, seq & 0xFF]) + payload
    frame = bytearray(SOF)
    frame.extend(len(body).to_bytes(2, "little"))
    frame.extend(body)
    frame.extend(crc16_modbus(frame).to_bytes(2, "little"))
    return bytes(frame)


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

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._session: SerialSession | None = None
        self._buffer = bytearray()
        self._seq = 0
        self._pending: _PendingRequest | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_once)

    @property
    def is_connected(self) -> bool:
        return self._session is not None and self._session.is_open

    @property
    def is_busy(self) -> bool:
        return self._pending is not None

    def attach_session(self, session: SerialSession) -> None:
        self._session = session
        self._buffer.clear()
        self._pending = None
        session.set_event_receiver(self)
        self.connectionChanged.emit(session.is_open)
        self.log.emit(f"Attached to serial session on {session.cfg.port}")

    def detach_session(self) -> None:
        if self._session is not None:
            try:
                self._session.set_event_receiver(None)
            except Exception:
                pass
        self._session = None
        self._buffer.clear()
        self._pending = None
        self.stop_polling()
        self.connectionChanged.emit(False)

    def start_polling(self, interval_ms: int = 800) -> None:
        self._poll_timer.start(max(200, int(interval_ms)))

    def stop_polling(self) -> None:
        self._poll_timer.stop()

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
        payload = b"".join(encode_tlv(type_id) for type_id in types)
        response = self._request(PowerCommand.READ, payload, timeout_ms=timeout_ms)

        if types == (PowerDataType.APP_TVL_DEBUG_SNAPSHOT,):
            return response

        missing = [type_id.name for type_id in types if type_id not in response]
        if missing:
            raise PowerClientProtocolError(f"Missing response types: {', '.join(missing)}")
        return response

    def write_values(self, values: dict[PowerDataType, bytes], timeout_ms: int = 1000) -> None:
        payload = b"".join(encode_tlv(type_id, raw_value) for type_id, raw_value in values.items())
        self._request(PowerCommand.WRITE, payload, timeout_ms=timeout_ms)

    def read_status(self, timeout_ms: int = 1000) -> PowerStatus:
        result = self.read_values(
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
            timeout_ms=timeout_ms,
        )
        status = PowerStatus(
            vin_mv=result[PowerDataType.INPUT_VOLTAGE],
            iin_ma=result[PowerDataType.INPUT_CURRENT],
            vout_mv=result[PowerDataType.OUTPUT_VOLTAGE],
            iout_ma=result[PowerDataType.OUTPUT_CURRENT],
            core_temp_mc=result[PowerDataType.CORE_TEMPERATURE],
            board_temp_mc=result[PowerDataType.BOARD_TEMPERATURE],
            set_voltage_limit_mv=result[PowerDataType.SET_VOLTAGE_LIMIT],
            set_current_limit_ma=result[PowerDataType.SET_CURRENT_LIMIT],
            cc_cv_mode=result[PowerDataType.CC_CV_MODE],
            power_state=result[PowerDataType.POWER_STATE],
            fault_state=result[PowerDataType.FAULT_STATE],
            state_machine_flag_bits=result[PowerDataType.STATE_MACHINE_FLAG_BITS],
            state_machine_state=result[PowerDataType.STATE_MACHINE_STATE],
            otp_value_mc=result[PowerDataType.OTP_VALUE],
            otp_set_value_mc=result[PowerDataType.OTP_SET_VALUE],
            ovp_value_mv=result[PowerDataType.OVP_VALUE],
            ovp_set_value_mv=result[PowerDataType.OVP_SET_VALUE],
            ocp_value_ma=result[PowerDataType.OCP_VALUE],
            ocp_set_value_ma=result[PowerDataType.OCP_SET_VALUE],
            fan_speed=result[PowerDataType.FAN_SPEED],
            fan_set_value=result[PowerDataType.FAN_SET_VALUE],
        )
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
        if not self.is_connected or self.is_busy:
            return
        try:
            self.read_status(timeout_ms=800)
        except Exception as exc:
            self.error.emit(str(exc))

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
