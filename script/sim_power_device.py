# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import math
import signal
import sys
import time
from dataclasses import dataclass
from enum import IntEnum

from PyQt5.QtCore import QCoreApplication, QIODevice, QObject, QTimer
from PyQt5.QtSerialPort import QSerialPort


class PowerCommand(IntEnum):
    ACK = 0x00
    READ = 0x01
    WRITE = 0x02
    REPORT = 0x03
    STREAM_START = 0x04
    STREAM_STOP = 0x05
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
    DUTY_CMD = 35
    PWM_A_COMPARE = 36
    PWM_D_COMPARE = 37
    FAN_SPEED = 38
    FAN_SET_VALUE = 39
    DEBUG_SNAPSHOT = 40
    LOOP_CURRENT_FEEDBACK = 41
    LOOP_CURRENT_REFERENCE = 42
    VOLTAGE_LOOP_CURRENT_REFERENCE = 43


SOF = b"\xAA\x55"
STREAM_CHANNEL_SEPARATOR = b"\xFE\xED"
STREAM_FAST_PERIOD_MS = 20
STREAM_SLOW_PERIOD_MS = 1000

STREAM_TYPES = (
    PowerDataType.INPUT_VOLTAGE,
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_VOLTAGE,
    PowerDataType.OUTPUT_CURRENT,
    PowerDataType.CORE_TEMPERATURE,
    PowerDataType.BOARD_TEMPERATURE,
    PowerDataType.FAN_SPEED,
    PowerDataType.FAN_SET_VALUE,
)

U8_TYPES = {
    PowerDataType.CC_CV_MODE,
    PowerDataType.POWER_STATE,
    PowerDataType.STATE_MACHINE_FLAG_BITS,
    PowerDataType.STATE_MACHINE_STATE,
}

SIGNED_TYPES = {
    PowerDataType.INPUT_CURRENT,
    PowerDataType.OUTPUT_CURRENT,
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
    PowerDataType.DUTY_CMD,
    PowerDataType.PWM_A_COMPARE,
    PowerDataType.PWM_D_COMPARE,
    PowerDataType.FAN_SPEED,
    PowerDataType.FAN_SET_VALUE,
)


@dataclass(frozen=True)
class Frame:
    cmd: int
    seq: int
    payload: bytes


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


def build_frame(cmd: PowerCommand | int, seq: int, payload: bytes = b"") -> bytes:
    body = bytes([int(cmd) & 0xFF, seq & 0xFF]) + bytes(payload)
    frame = bytearray(SOF)
    frame.extend(len(body).to_bytes(2, "little"))
    frame.extend(body)
    frame.extend(crc16_modbus(frame).to_bytes(2, "little"))
    return bytes(frame)


def value_length(type_id: PowerDataType) -> int:
    return 1 if type_id in U8_TYPES else 4


def encode_value(type_id: PowerDataType, value: int) -> bytes:
    length = value_length(type_id)
    return int(value).to_bytes(length, "little", signed=type_id in SIGNED_TYPES)


def decode_value(type_id: PowerDataType, raw: bytes) -> int:
    return int.from_bytes(raw, "little", signed=type_id in SIGNED_TYPES)


def encode_stream_value(type_id: PowerDataType, value: int) -> bytes:
    if type_id not in STREAM_TYPES:
        raise ValueError(f"{type_id.name} is not configured for raw stream")
    return int(value).to_bytes(2, "little", signed=False)


def encode_tlv(type_id: PowerDataType, value: bytes = b"") -> bytes:
    return bytes([int(type_id)]) + len(value).to_bytes(2, "little") + value


def parse_tlv_types(payload: bytes, *, allow_values: bool = False) -> list[tuple[PowerDataType, bytes]]:
    offset = 0
    result: list[tuple[PowerDataType, bytes]] = []
    while offset < len(payload):
        if offset + 3 > len(payload):
            raise ValueError("incomplete TLV header")
        raw_type = payload[offset]
        offset += 1
        length = int.from_bytes(payload[offset:offset + 2], "little")
        offset += 2
        if offset + length > len(payload):
            raise ValueError(f"incomplete TLV value for type {raw_type}")
        raw_value = payload[offset:offset + length]
        offset += length
        type_id = PowerDataType(raw_type)
        if not allow_values and length != 0:
            raise ValueError(f"query TLV {type_id.name} length should be 0")
        result.append((type_id, raw_value))
    return result


class FrameParser:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def input_bytes(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        frames: list[Frame] = []
        while True:
            while len(self.buffer) >= 2 and self.buffer[:2] != SOF:
                self.buffer.pop(0)

            if len(self.buffer) < 6:
                return frames

            body_len = int.from_bytes(self.buffer[2:4], "little")
            total_len = 2 + 2 + body_len + 2
            if len(self.buffer) < total_len:
                return frames

            raw = bytes(self.buffer[:total_len])
            del self.buffer[:total_len]

            recv_crc = int.from_bytes(raw[-2:], "little")
            calc_crc = crc16_modbus(raw[:-2])
            if recv_crc != calc_crc or body_len < 2:
                continue

            frames.append(Frame(cmd=raw[4], seq=raw[5], payload=raw[6:-2]))


class SimPowerDevice(QObject):
    def __init__(
        self,
        port: str,
        baudrate: int,
        *,
        fault_mode: str = "normal",
        fault_count: int = 0,
        fault_command: str = "all",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.serial = QSerialPort(self)
        self.serial.setPortName(port)
        self.serial.setBaudRate(baudrate)
        self.serial.setDataBits(QSerialPort.DataBits.Data8)
        self.serial.setParity(QSerialPort.Parity.NoParity)
        self.serial.setStopBits(QSerialPort.StopBits.OneStop)
        self.serial.readyRead.connect(self._on_ready_read)
        self.serial.errorOccurred.connect(self._on_error)

        self.parser = FrameParser()
        self.stream_timer = QTimer(self)
        self.stream_timer.timeout.connect(self._send_stream_sample)
        self.stream_fast_types: tuple[PowerDataType, ...] = (
            PowerDataType.INPUT_VOLTAGE,
            PowerDataType.INPUT_CURRENT,
            PowerDataType.OUTPUT_VOLTAGE,
            PowerDataType.OUTPUT_CURRENT,
        )
        self.stream_slow_types: tuple[PowerDataType, ...] = (
            PowerDataType.CORE_TEMPERATURE,
            PowerDataType.BOARD_TEMPERATURE,
            PowerDataType.FAN_SPEED,
            PowerDataType.FAN_SET_VALUE,
        )
        self.stream_fast_samples_until_slow = 0
        self.stream_slow_every_fast_samples = STREAM_SLOW_PERIOD_MS // STREAM_FAST_PERIOD_MS
        self.started_at = time.monotonic()
        self.tick = 0
        self.values = self._initial_values()
        self.fault_mode = fault_mode
        self.fault_count = max(0, int(fault_count))
        self.fault_command = fault_command

    def open(self) -> None:
        if not self.serial.open(QIODevice.OpenModeFlag.ReadWrite):
            raise RuntimeError(f"open {self.serial.portName()} failed: {self.serial.errorString()}")
        print(f"Sim power device listening on {self.serial.portName()} @ {self.serial.baudRate()}")
        if self.fault_mode != "normal" and self.fault_count > 0:
            print(
                f"fault injection enabled: mode={self.fault_mode}, "
                f"count={self.fault_count}, command={self.fault_command}"
            )

    def close(self) -> None:
        self.stream_timer.stop()
        if self.serial.isOpen():
            self.serial.close()

    def _initial_values(self) -> dict[PowerDataType, int]:
        return {
            PowerDataType.INPUT_VOLTAGE: 24000,
            PowerDataType.INPUT_CURRENT: 700,
            PowerDataType.OUTPUT_VOLTAGE: 12000,
            PowerDataType.OUTPUT_CURRENT: 500,
            PowerDataType.CORE_TEMPERATURE: 35000,
            PowerDataType.BOARD_TEMPERATURE: 32000,
            PowerDataType.SET_VOLTAGE_LIMIT: 12000,
            PowerDataType.SET_CURRENT_LIMIT: 3000,
            PowerDataType.CC_CV_MODE: 1,
            PowerDataType.POWER_STATE: 1,
            PowerDataType.FAULT_STATE: 0,
            PowerDataType.STATE_MACHINE_FLAG_BITS: 0x08,
            PowerDataType.STATE_MACHINE_STATE: 1,
            PowerDataType.INPUT_VOLTAGE_RAW: 3000,
            PowerDataType.INPUT_CURRENT_RAW: 1200,
            PowerDataType.OUTPUT_VOLTAGE_RAW: 2500,
            PowerDataType.OUTPUT_CURRENT_RAW: 900,
            PowerDataType.OTP_VALUE: 32000,
            PowerDataType.OTP_SET_VALUE: 85000,
            PowerDataType.OVP_VALUE: 12000,
            PowerDataType.OVP_SET_VALUE: 44000,
            PowerDataType.OCP_VALUE: 500,
            PowerDataType.OCP_SET_VALUE: 3500,
            PowerDataType.DUTY_CMD: 420,
            PowerDataType.PWM_A_COMPARE: 15080,
            PowerDataType.PWM_D_COMPARE: 1560,
            PowerDataType.FAN_SPEED: 650,
            PowerDataType.FAN_SET_VALUE: 700,
            PowerDataType.LOOP_CURRENT_FEEDBACK: 500,
            PowerDataType.LOOP_CURRENT_REFERENCE: 3000,
            PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE: 12000,
        }

    def _on_ready_read(self) -> None:
        raw = self.serial.readAll()
        data = raw.data() if hasattr(raw, "data") else bytes(raw)
        if not data:
            return
        print(f"RX {data.hex(' ')}")
        for frame in self.parser.input_bytes(data):
            self._handle_frame(frame)

    def _on_error(self, error) -> None:
        if error == QSerialPort.SerialPortError.NoError:
            return
        print(f"serial error: {self.serial.errorString()}", file=sys.stderr)

    def _write(self, data: bytes) -> None:
        self.serial.write(data)
        self.serial.waitForBytesWritten(100)
        print(f"TX {data.hex(' ')}")

    def _send_ack(self, seq: int, payload: bytes = b"") -> None:
        self._write(build_frame(PowerCommand.ACK, seq, payload))

    def _send_nack(self, seq: int, reason: str) -> None:
        print(f"NACK seq={seq}: {reason}")
        self._write(build_frame(PowerCommand.NACK, seq, b""))

    def _send_bad_crc(self, seq: int) -> None:
        frame = bytearray(build_frame(PowerCommand.ACK, seq, b""))
        frame[-1] ^= 0xFF
        print(f"BAD_CRC seq={seq}")
        self._write(bytes(frame))

    def _should_fault(self, cmd: PowerCommand) -> bool:
        if self.fault_mode == "normal" or self.fault_count <= 0:
            return False
        if self.fault_command != "all" and self.fault_command != cmd.name.lower():
            return False
        self.fault_count -= 1
        return True

    def _inject_fault(self, frame: Frame, cmd: PowerCommand) -> bool:
        if not self._should_fault(cmd):
            return False
        if cmd == PowerCommand.STREAM_START:
            self.stream_timer.stop()

        if self.fault_mode == "drop":
            print(f"DROP seq={frame.seq} cmd={cmd.name}")
            return True
        if self.fault_mode == "nack":
            self._send_nack(frame.seq, "injected fault")
            return True
        if self.fault_mode == "bad-crc":
            self._send_bad_crc(frame.seq)
            return True
        if self.fault_mode == "close":
            print(f"CLOSE seq={frame.seq} cmd={cmd.name}")
            self.close()
            return True
        return False

    def _handle_frame(self, frame: Frame) -> None:
        try:
            cmd = PowerCommand(frame.cmd)
        except ValueError:
            self._send_nack(frame.seq, f"unknown cmd 0x{frame.cmd:02X}")
            return

        print(f"FRAME cmd={cmd.name} seq={frame.seq} payload={frame.payload.hex(' ')}")
        if self._inject_fault(frame, cmd):
            return
        try:
            if cmd == PowerCommand.READ:
                self._handle_read(frame)
            elif cmd == PowerCommand.REPORT:
                self._handle_report(frame)
            elif cmd == PowerCommand.WRITE:
                self._handle_write(frame)
            elif cmd == PowerCommand.STREAM_START:
                self._handle_stream_start(frame)
            elif cmd == PowerCommand.STREAM_STOP:
                self.stream_timer.stop()
                self._send_ack(frame.seq)
            else:
                self._send_nack(frame.seq, f"unsupported host cmd {cmd.name}")
        except Exception as exc:
            self._send_nack(frame.seq, str(exc))

    def _handle_read(self, frame: Frame) -> None:
        items = parse_tlv_types(frame.payload)
        response = bytearray()
        for type_id, _ in items:
            if type_id == PowerDataType.DEBUG_SNAPSHOT:
                for debug_type in (
                    PowerDataType.OUTPUT_VOLTAGE_RAW,
                    PowerDataType.OUTPUT_VOLTAGE,
                    PowerDataType.INPUT_CURRENT_RAW,
                    PowerDataType.OUTPUT_CURRENT_RAW,
                    PowerDataType.INPUT_CURRENT,
                    PowerDataType.OUTPUT_CURRENT,
                    PowerDataType.LOOP_CURRENT_FEEDBACK,
                    PowerDataType.LOOP_CURRENT_REFERENCE,
                    PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE,
                ):
                    response.extend(self._tlv_value(debug_type))
            else:
                response.extend(self._tlv_value(type_id))
        self._send_ack(frame.seq, bytes(response))

    def _handle_report(self, frame: Frame) -> None:
        payload = b"".join(self._tlv_value(type_id) for type_id in STATUS_TYPES)
        self._write(build_frame(PowerCommand.REPORT, frame.seq, payload))

    def _handle_write(self, frame: Frame) -> None:
        for type_id, raw_value in parse_tlv_types(frame.payload, allow_values=True):
            expected = value_length(type_id)
            if len(raw_value) != expected:
                raise ValueError(f"{type_id.name} length {len(raw_value)} != {expected}")
            self.values[type_id] = decode_value(type_id, raw_value)
        self._send_ack(frame.seq)

    def _handle_stream_start(self, frame: Frame) -> None:
        fast_period_ms, fast_types, slow_period_ms, slow_types = self._parse_stream_start_payload(frame.payload)
        self.stream_fast_types = fast_types
        self.stream_slow_types = slow_types
        self.stream_slow_every_fast_samples = max(1, slow_period_ms // fast_period_ms) if slow_types else 0
        self.stream_fast_samples_until_slow = 0
        self._send_ack(frame.seq)
        self.stream_timer.start(max(1, fast_period_ms))
        print(
            f"stream started fast={fast_period_ms}ms "
            f"types={','.join(type_id.name for type_id in self.stream_fast_types)}; "
            f"slow={slow_period_ms}ms "
            f"types={','.join(type_id.name for type_id in self.stream_slow_types)}"
        )

    def _parse_stream_start_payload(
        self,
        payload: bytes,
    ) -> tuple[int, tuple[PowerDataType, ...], int, tuple[PowerDataType, ...]]:
        if len(payload) < 3:
            raise ValueError("STREAM_START payload missing fast group")
        offset = 0
        fast_period_ms = int.from_bytes(payload[offset:offset + 2], "little")
        offset += 2
        fast_count = payload[offset]
        offset += 1
        fast_end = offset + fast_count * 3
        if fast_count <= 0 or fast_end > len(payload):
            raise ValueError("STREAM_START fast group length is invalid")
        fast_types = tuple(type_id for type_id, _ in parse_tlv_types(payload[offset:fast_end]))
        offset = fast_end

        slow_period_ms = 0
        slow_types: tuple[PowerDataType, ...] = ()
        if offset < len(payload):
            if offset + 3 > len(payload):
                raise ValueError("STREAM_START payload missing slow group")
            slow_period_ms = int.from_bytes(payload[offset:offset + 2], "little")
            offset += 2
            slow_count = payload[offset]
            offset += 1
            slow_end = offset + slow_count * 3
            if slow_end != len(payload):
                raise ValueError("STREAM_START slow group length is invalid")
            slow_types = tuple(type_id for type_id, _ in parse_tlv_types(payload[offset:slow_end]))

        if slow_types and (slow_period_ms <= 0 or slow_period_ms % fast_period_ms != 0):
            raise ValueError("slow period must be a positive integer multiple of fast period")
        return fast_period_ms, fast_types, slow_period_ms, slow_types

    def _tlv_value(self, type_id: PowerDataType) -> bytes:
        value = encode_value(type_id, self.values.get(type_id, 0))
        return encode_tlv(type_id, value)

    def _send_stream_sample(self) -> None:
        self._update_dynamic_values()
        sample = bytearray()
        sample.extend(self._pack_stream_group(self.stream_fast_types))
        if self.stream_slow_types and self.stream_fast_samples_until_slow <= 0:
            sample.extend(self._pack_stream_group(self.stream_slow_types))
            self.stream_fast_samples_until_slow = self.stream_slow_every_fast_samples - 1
        elif self.stream_slow_types:
            self.stream_fast_samples_until_slow -= 1
        self._write(bytes(sample))

    def _pack_stream_group(self, types: tuple[PowerDataType, ...]) -> bytes:
        sample = bytearray()
        for index, type_id in enumerate(types):
            sample.extend(encode_stream_value(type_id, self.values.get(type_id, 0)))
            if index < len(types) - 1:
                sample.extend(STREAM_CHANNEL_SEPARATOR)
        return bytes(sample)

    def _update_dynamic_values(self) -> None:
        self.tick += 1
        phase = (time.monotonic() - self.started_at) * 2.0
        enabled = bool(self.values.get(PowerDataType.POWER_STATE, 0))
        target_v = self.values.get(PowerDataType.SET_VOLTAGE_LIMIT, 12000) if enabled else 0
        target_i = min(self.values.get(PowerDataType.SET_CURRENT_LIMIT, 3000), 500 + int(120 * math.sin(phase)))
        self.values[PowerDataType.OUTPUT_VOLTAGE] = max(0, target_v + int(80 * math.sin(phase)))
        self.values[PowerDataType.OUTPUT_CURRENT] = max(0, target_i if enabled else 0)
        self.values[PowerDataType.INPUT_CURRENT] = max(0, int(self.values[PowerDataType.OUTPUT_CURRENT] * 0.55) + 120)
        self.values[PowerDataType.CORE_TEMPERATURE] = 35000 + int(1500 * math.sin(phase / 4.0))
        self.values[PowerDataType.BOARD_TEMPERATURE] = 32000 + int(1000 * math.sin(phase / 5.0))
        self.values[PowerDataType.FAN_SPEED] = min(1000, max(0, self.values.get(PowerDataType.FAN_SET_VALUE, 700)))
        self.values[PowerDataType.OVP_VALUE] = self.values[PowerDataType.OUTPUT_VOLTAGE]
        self.values[PowerDataType.OCP_VALUE] = self.values[PowerDataType.OUTPUT_CURRENT]
        self.values[PowerDataType.OTP_VALUE] = self.values[PowerDataType.BOARD_TEMPERATURE]
        self.values[PowerDataType.DUTY_CMD] = 420 + int(20 * math.sin(phase))
        self.values[PowerDataType.PWM_A_COMPARE] = 15080 + self.values[PowerDataType.DUTY_CMD]
        self.values[PowerDataType.PWM_D_COMPARE] = 1560 + self.values[PowerDataType.DUTY_CMD] // 4
        self.values[PowerDataType.OUTPUT_VOLTAGE_RAW] = self.values[PowerDataType.OUTPUT_VOLTAGE] // 5
        self.values[PowerDataType.OUTPUT_CURRENT_RAW] = self.values[PowerDataType.OUTPUT_CURRENT] // 2
        self.values[PowerDataType.INPUT_CURRENT_RAW] = self.values[PowerDataType.INPUT_CURRENT] // 2
        self.values[PowerDataType.LOOP_CURRENT_FEEDBACK] = self.values[PowerDataType.OUTPUT_CURRENT]
        self.values[PowerDataType.LOOP_CURRENT_REFERENCE] = self.values.get(PowerDataType.SET_CURRENT_LIMIT, 3000)
        self.values[PowerDataType.VOLTAGE_LOOP_CURRENT_REFERENCE] = self.values.get(PowerDataType.SET_VOLTAGE_LIMIT, 12000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate F4CP lower power device on a serial port.")
    parser.add_argument("--port", default="COM9", help="simulator serial port, default: COM9")
    parser.add_argument("--baudrate", type=int, default=921600, help="baudrate, default: 921600")
    parser.add_argument(
        "--fault-mode",
        choices=("normal", "drop", "nack", "bad-crc", "close"),
        default="normal",
        help="inject response faults for PowerPage disconnect testing",
    )
    parser.add_argument(
        "--fault-count",
        type=int,
        default=0,
        help="number of matching requests to fault; use 3 to test auto disconnect",
    )
    parser.add_argument(
        "--fault-command",
        choices=("all", "read", "write", "report", "stream_start", "stream_stop"),
        default="all",
        help="host command to fault; default faults all commands",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QCoreApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(200)

    device = SimPowerDevice(
        args.port,
        args.baudrate,
        fault_mode=args.fault_mode,
        fault_count=args.fault_count,
        fault_command=args.fault_command,
    )
    try:
        device.open()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    app.aboutToQuit.connect(device.close)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
