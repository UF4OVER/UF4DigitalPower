# -*- coding: utf-8 -*-
"""Synchronous UF4COM host helper for scripts and manual power tests."""

from __future__ import annotations

import time

from PyQt5.QtCore import QIODevice
from PyQt5.QtSerialPort import QSerialPort

from app.core.const import (
    PowerClientError,
    PowerClientDeviceError,
    PowerClientProtocolError,
    PowerClientTimeoutError,
    PowerCommand,
    PowerDataType,
    PowerFrameFlag,
    STATUS_READ_TYPES,
)
from app.protocol.tvlcom import (
    build_frame,
    decode_tlvs,
    encode_tlv,
    ensure_readable,
    ensure_writable,
    extract_frame_from_buffer,
)


def _u32(value: int) -> bytes:
    return int(value).to_bytes(4, "little", signed=False)


def _u8(value: int) -> bytes:
    return int(value).to_bytes(1, "little", signed=False)


def _u16(value: int) -> bytes:
    return int(value).to_bytes(2, "little", signed=False)


class TVLHost:
    """Reusable QSerialPort host for the F4CP power protocol."""

    def __init__(self, port: str, baudrate: int = 921600, timeout: float = 1.0):
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
            frame = extract_frame_from_buffer(self._buffer)
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
            ensure_readable(type_id)
        payload = b"".join(encode_tlv(type_id) for type_id in types)
        values = self._request(
            PowerCommand.READ,
            payload,
            timeout=timeout,
            expected_cmd=PowerCommand.READ_RSP,
        )
        missing = [type_id.name for type_id in types if type_id not in values]
        if missing:
            raise PowerClientProtocolError(f"Missing response types: {', '.join(missing)}")
        self._last_values.update(values)
        return values

    def read_report_values(self, timeout: float | None = None) -> dict[PowerDataType, int]:
        values = self.read_values(*STATUS_READ_TYPES, timeout=timeout)
        missing = [type_id.name for type_id in STATUS_READ_TYPES if type_id not in values]
        if missing:
            raise PowerClientProtocolError(f"Missing report types: {', '.join(missing)}")
        self._last_values.update(values)
        return values

    def write_values(
        self,
        values: dict[PowerDataType, bytes],
        timeout: float | None = None,
    ) -> None:
        for type_id, raw_value in values.items():
            ensure_writable(type_id, raw_value)
        payload = b"".join(encode_tlv(type_id, raw_value) for type_id, raw_value in values.items())
        self._request(
            PowerCommand.WRITE,
            payload,
            timeout=timeout,
            expected_cmd=PowerCommand.WRITE_RSP,
        )
        self._last_values.update(
            {
                type_id: int.from_bytes(raw_value, "little", signed=False)
                for type_id, raw_value in values.items()
            }
        )

    def read_status(self, timeout: float | None = None):
        from app.session.session_power import build_status

        return build_status(self.read_report_values(timeout=timeout))

    def set_voltage_limit_mv(self, value_mv: int) -> None:
        self.write_values({PowerDataType.SET_VOLTAGE_LIMIT: _u32(value_mv)})

    def set_current_limit_ma(self, value_ma: int) -> None:
        self.write_values({PowerDataType.SET_CURRENT_LIMIT: _u32(value_ma)})

    def set_ovp_mv(self, value_mv: int) -> None:
        self.write_values({PowerDataType.OVP_SET_VALUE: _u32(value_mv)})

    def set_ocp_ma(self, value_ma: int) -> None:
        self.write_values({PowerDataType.OCP_SET_VALUE: _u32(value_ma)})

    def set_otp_mc(self, value_mc: int) -> None:
        self.write_values({PowerDataType.OTP_SET_VALUE: _u16(value_mc)})

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
        expected_cmd: PowerCommand,
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
            flags = int(frame.get("flags", 0))

            if frame_cmd == int(PowerCommand.STREAM_DATA):
                self._handle_stream_data_frame(frame)
                continue
            if flags & int(PowerFrameFlag.ERROR):
                payload = bytes(frame["payload"])
                code = int.from_bytes(payload[1:3], "big", signed=False) if len(payload) >= 3 else 0
                raise PowerClientDeviceError(f"Device returned UF4COM error 0x{code:04X} for seq={frame['seq']}")
            if frame_cmd != int(expected_cmd):
                raise PowerClientProtocolError(f"Unexpected response cmd=0x{frame_cmd:02X}")
            if int(frame["seq"]) != seq:
                raise PowerClientProtocolError(
                    f"Response seq mismatch: expected {seq}, got {frame['seq']}"
                )
            return decode_tlvs(bytes(frame["payload"]))

    def _handle_stream_data_frame(self, frame: dict[str, int | bytes]) -> None:
        self._last_values.update(decode_tlvs(bytes(frame["payload"]), strict=False))
